plugins {
    id("com.android.library")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "ai.shufu.sdk"
    compileSdk = 35
    ndkVersion = "27.2.12479018"

    defaultConfig {
        minSdk = 26
        testInstrumentationRunner = "android.test.InstrumentationTestRunner"
        consumerProguardFiles("consumer-rules.pro")
        ndk {
            // v0.2 intentionally publishes one tested ABI; broaden only after
            // adding matching native builds and device coverage.
            abiFilters += listOf("arm64-v8a")
        }
        externalNativeBuild {
            cmake {
                cppFlags += listOf("-std=c++17", "-O3", "-fexceptions", "-frtti")
                arguments += listOf("-DANDROID_STL=c++_shared")
                // Allows a verified offline llama.cpp archive without changing
                // the pinned URL/hash logic in CMakeLists.txt.
                providers.gradleProperty("shufuLlamaArchive").orNull?.let { archive ->
                    arguments += "-DSHUFU_LLAMA_ARCHIVE=$archive"
                }
            }
        }
    }

    externalNativeBuild {
        cmake {
            path = file("src/main/cpp/CMakeLists.txt")
            version = "3.22.1"
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    testOptions {
        unitTests.isReturnDefaultValues = true
    }
}

dependencies {
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20240303")
}
