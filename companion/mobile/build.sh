#!/bin/bash
# 构建 AI Companion Android APK
# 需要：JDK + Android SDK（ANDROID_HOME）

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/android"

# 检查环境
if [ -z "$ANDROID_HOME" ]; then
    # macOS Homebrew 默认路径
    if [ -d "$HOME/Library/Android/sdk" ]; then
        export ANDROID_HOME="$HOME/Library/Android/sdk"
    elif command -v sdkmanager &>/dev/null; then
        export ANDROID_HOME="$(dirname "$(which sdkmanager)")/../.."
    else
        echo "❌ 未找到 Android SDK"
        echo "请安装 Android SDK 或设置 ANDROID_HOME"
        exit 1
    fi
fi

echo "📱 Android SDK: $ANDROID_HOME"
echo "☕ Java: $(java -version 2>&1 | head -1)"

# 接受 licenses（自动）
yes | "$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" --licenses 2>/dev/null || true

# 安装必需的 SDK 组件
"$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" \
    "platforms;android-34" \
    "build-tools;34.0.0" \
    "platform-tools" 2>/dev/null || true

# 构建
echo ""
echo "🔨 构建 APK..."
chmod +x gradlew 2>/dev/null || true
./gradlew assembleDebug --quiet

APK_PATH="app/build/outputs/apk/debug/app-debug.apk"
if [ -f "$APK_PATH" ]; then
    SIZE=$(du -h "$APK_PATH" | cut -f1)
    echo ""
    echo "✅ APK 构建成功: $APK_PATH ($SIZE)"
    echo ""
    echo "安装到设备: adb install $APK_PATH"
else
    echo "❌ APK 未生成"
    exit 1
fi
