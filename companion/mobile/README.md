# AI Companion Android App

WebView 壳 + 现有 WebUI，打包成 Android APK。

## 构建

```bash
cd companion/mobile/android
./gradlew assembleDebug
```

APK 输出：`app/build/outputs/apk/debug/app-debug.apk`

## 安装

```bash
adb install app/build/outputs/apk/debug/app-debug.apk
```

## 服务器地址

默认连接 `http://10.0.2.2:8080`（Android 模拟器连接宿主机的 localhost）。

真机使用：把 `MainActivity.java` 中的 `SERVER_URL` 改为你 Mac 的局域网 IP，例如：
```java
private static final String SERVER_URL = "http://192.168.1.100:8080";
```

## 功能

- 全屏 WebView，无状态栏/导航栏
- JavaScript + LocalStorage 启用（持久化对话）
- 下拉刷新
- 返回键处理（WebView 历史后退）
- 加载进度条
