#include <jni.h>
#include <android/log.h>

#include "ggml-backend.h"
#include "llama.h"

#include <algorithm>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

constexpr const char * TAG = "ShuFuLlama";

struct ModelHandle {
    // The model is long-lived; each generation creates a short-lived context.
    // The mutex serializes generation because llama.cpp state is not exposed as
    // independently safe through this minimal v0.2 Kotlin API.
    llama_model * model = nullptr;
    const llama_vocab * vocab = nullptr;
    std::mutex mutex;

    ~ModelHandle() {
        if (model != nullptr) {
            llama_model_free(model);
        }
    }
};

std::once_flag backend_once;

// JNI entry points translate native failures into one predictable Java type so
// Android callers never need to inspect C++ status codes or leaked exceptions.
void throw_java(JNIEnv * env, const char * type, const std::string & message) {
    jclass cls = env->FindClass(type);
    if (cls != nullptr) {
        env->ThrowNew(cls, message.c_str());
    }
}

std::string from_jstring(JNIEnv * env, jstring value) {
    // NewStringUTF uses modified UTF-8, so conversion through String.getBytes
    // preserves ordinary UTF-8 prompts, including Chinese text and emoji.
    if (value == nullptr) return {};
    jclass string_class = env->FindClass("java/lang/String");
    jmethodID get_bytes = env->GetMethodID(string_class, "getBytes", "(Ljava/lang/String;)[B");
    jstring charset = env->NewStringUTF("UTF-8");
    auto bytes = static_cast<jbyteArray>(env->CallObjectMethod(value, get_bytes, charset));
    env->DeleteLocalRef(charset);
    env->DeleteLocalRef(string_class);
    if (bytes == nullptr || env->ExceptionCheck()) return {};
    const jsize length = env->GetArrayLength(bytes);
    std::string result(static_cast<size_t>(length), '\0');
    if (length > 0) {
        env->GetByteArrayRegion(bytes, 0, length, reinterpret_cast<jbyte *>(result.data()));
    }
    env->DeleteLocalRef(bytes);
    return result;
}

jstring to_jstring(JNIEnv * env, const std::string & value) {
    jbyteArray bytes = env->NewByteArray(static_cast<jsize>(value.size()));
    if (bytes == nullptr) return nullptr;
    if (!value.empty()) {
        env->SetByteArrayRegion(
            bytes,
            0,
            static_cast<jsize>(value.size()),
            reinterpret_cast<const jbyte *>(value.data())
        );
    }
    jclass string_class = env->FindClass("java/lang/String");
    jmethodID constructor = env->GetMethodID(string_class, "<init>", "([BLjava/lang/String;)V");
    jstring charset = env->NewStringUTF("UTF-8");
    auto result = static_cast<jstring>(env->NewObject(string_class, constructor, bytes, charset));
    env->DeleteLocalRef(charset);
    env->DeleteLocalRef(bytes);
    env->DeleteLocalRef(string_class);
    return result;
}

ModelHandle * as_handle(jlong value) {
    // Handles never cross processes and are zeroed by the Kotlin owner on close.
    return reinterpret_cast<ModelHandle *>(value);
}

} // namespace

extern "C" JNIEXPORT jlong JNICALL
Java_ai_shufu_sdk_local_LlamaCppRuntime_nativeLoadModel(
    JNIEnv * env,
    jobject,
    jstring model_path
) {
    try {
        // Backend discovery is process-wide and must happen only once even when
        // an application replaces models during its lifetime.
        std::call_once(backend_once, [] { ggml_backend_load_all(); });
        const std::string path = from_jstring(env, model_path);
        if (path.empty()) throw std::invalid_argument("model path must not be empty");

        llama_model_params params = llama_model_default_params();
        // v0.2 targets a predictable CPU-only ARM64 baseline.
        params.n_gpu_layers = 0;
        auto handle = std::make_unique<ModelHandle>();
        handle->model = llama_model_load_from_file(path.c_str(), params);
        if (handle->model == nullptr) {
            throw std::runtime_error("Unable to load GGUF model: " + path);
        }
        handle->vocab = llama_model_get_vocab(handle->model);
        __android_log_print(ANDROID_LOG_INFO, TAG, "Loaded model %s", path.c_str());
        return reinterpret_cast<jlong>(handle.release());
    } catch (const std::exception & error) {
        throw_java(env, "java/lang/IllegalStateException", error.what());
        return 0;
    }
}

extern "C" JNIEXPORT jstring JNICALL
Java_ai_shufu_sdk_local_LlamaCppRuntime_nativeGenerate(
    JNIEnv * env,
    jobject,
    jlong native_handle,
    jstring prompt_value,
    jint max_tokens
) {
    auto * handle = as_handle(native_handle);
    if (handle == nullptr || handle->model == nullptr) {
        throw_java(env, "java/lang/IllegalStateException", "No local model is loaded");
        return nullptr;
    }
    try {
        std::lock_guard<std::mutex> lock(handle->mutex);
        const std::string prompt = from_jstring(env, prompt_value);
        if (prompt.empty()) throw std::invalid_argument("prompt must not be empty");
        const int predict = std::clamp<int>(max_tokens, 1, 2048);

        // First call asks llama.cpp for the required capacity; the second fills
        // the exact-sized token buffer and avoids a guessed fixed limit.
        const int token_count = -llama_tokenize(
            handle->vocab,
            prompt.c_str(),
            static_cast<int32_t>(prompt.size()),
            nullptr,
            0,
            true,
            true
        );
        if (token_count <= 0) throw std::runtime_error("Unable to tokenize prompt");
        std::vector<llama_token> tokens(static_cast<size_t>(token_count));
        if (llama_tokenize(
                handle->vocab,
                prompt.c_str(),
                static_cast<int32_t>(prompt.size()),
                tokens.data(),
                static_cast<int32_t>(tokens.size()),
                true,
                true) < 0) {
            throw std::runtime_error("Unable to tokenize prompt");
        }

        llama_context_params context_params = llama_context_default_params();
        // The context holds the entire prompt plus the bounded generation budget.
        context_params.n_ctx = static_cast<uint32_t>(std::max(512, token_count + predict));
        context_params.n_batch = static_cast<uint32_t>(token_count);
        context_params.no_perf = true;
        std::unique_ptr<llama_context, decltype(&llama_free)> context(
            llama_init_from_model(handle->model, context_params),
            llama_free
        );
        if (!context) throw std::runtime_error("Unable to create llama context");

        llama_sampler_chain_params sampler_params = llama_sampler_chain_default_params();
        sampler_params.no_perf = true;
        std::unique_ptr<llama_sampler, decltype(&llama_sampler_free)> sampler(
            llama_sampler_chain_init(sampler_params),
            llama_sampler_free
        );
        // Greedy decoding keeps the first Android release deterministic. Sampling
        // controls can be added later without changing the JNI handle lifecycle.
        llama_sampler_chain_add(sampler.get(), llama_sampler_init_greedy());

        llama_batch batch = llama_batch_get_one(tokens.data(), static_cast<int32_t>(tokens.size()));
        if (llama_decode(context.get(), batch) != 0) {
            throw std::runtime_error("Prompt evaluation failed");
        }

        std::string output;
        output.reserve(static_cast<size_t>(predict) * 4);
        for (int generated = 0; generated < predict; ++generated) {
            llama_token token = llama_sampler_sample(sampler.get(), context.get(), -1);
            if (llama_vocab_is_eog(handle->vocab, token)) break;
            std::vector<char> piece(256);
            int length = llama_token_to_piece(
                handle->vocab,
                token,
                piece.data(),
                static_cast<int32_t>(piece.size()),
                0,
                true
            );
            if (length < 0) {
                piece.resize(static_cast<size_t>(-length));
                length = llama_token_to_piece(
                    handle->vocab,
                    token,
                    piece.data(),
                    static_cast<int32_t>(piece.size()),
                    0,
                    true
                );
            }
            if (length > 0) output.append(piece.data(), static_cast<size_t>(length));
            batch = llama_batch_get_one(&token, 1);
            if (llama_decode(context.get(), batch) != 0) break;
        }
        return to_jstring(env, output);
    } catch (const std::exception & error) {
        throw_java(env, "java/lang/IllegalStateException", error.what());
        return nullptr;
    }
}

extern "C" JNIEXPORT void JNICALL
Java_ai_shufu_sdk_local_LlamaCppRuntime_nativeClose(
    JNIEnv *,
    jobject,
    jlong native_handle
) {
    delete as_handle(native_handle);
}

extern "C" JNIEXPORT jstring JNICALL
Java_ai_shufu_sdk_local_LlamaCppRuntime_nativeVersion(JNIEnv * env, jobject) {
    return env->NewStringUTF("llama.cpp " SHUFU_LLAMA_VERSION);
}
