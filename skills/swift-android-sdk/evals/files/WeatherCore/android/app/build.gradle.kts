plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.example.weather"
    compileSdk = 35
    defaultConfig {
        applicationId = "com.example.weather"
        minSdk = 28
        targetSdk = 35
        ndk { abiFilters += listOf("arm64-v8a") }
    }
}

// Builds the Swift package for Android and drops the library into jniLibs.
val swiftPackage = rootProject.file("../swift")
val buildSwift by tasks.registering(Exec::class) {
    workingDir = swiftPackage
    commandLine("swift", "build", "-c", "release", "--swift-sdk", "aarch64-unknown-linux-android28")
}
val copySwiftLibraries by tasks.registering(Copy::class) {
    dependsOn(buildSwift)
    from(swiftPackage.resolve(".build/aarch64-unknown-linux-android28/release")) {
        include("libWeatherCore.so")
    }
    into("src/main/jniLibs/arm64-v8a")
}
tasks.named("preBuild") { dependsOn(copySwiftLibraries) }
