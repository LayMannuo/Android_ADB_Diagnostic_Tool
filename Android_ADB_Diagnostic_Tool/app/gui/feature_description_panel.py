from PySide6.QtWidgets import QGroupBox, QTextEdit, QVBoxLayout


class FeatureDescriptionPanel(QGroupBox):
    def __init__(self):
        super().__init__("功能说明与页面布局")
        layout = QVBoxLayout(self)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText(
            "\n".join(
                [
                    "页面 1：快速诊断",
                    "  - 设备状态区：显示 ADB、连接、授权、型号、Android 版本、root、remount、IP 摘要。",
                    "  - 小白解释：root/remount 是工程师权限，普通客户不懂也没关系；失败通常是设备固件限制，不代表工具坏了。",
                    "  - IP 摘要：用于快速判断设备是否拿到网络地址；没有 IP 时优先抓网络日志或完整诊断包。",
                    "  - 一键诊断：客户填写问题信息后，自动抓取完整日志并生成 zip。",
                    "  - ADB 投屏：调用内置 scrcpy 投屏；客户直接运行 exe 即可，不需要单独安装 scrcpy。",
                    "  - 截屏/录屏：录屏默认 10 秒，可手动修改 1~180 秒，按钮显示为“录制屏幕”。",
                    "  - ADB 调试窗口：FAE 可直接输入 ADB 命令。默认进入 adb shell 简易模式；需要完整交互时会打开真实 CMD Shell。",
                    "",
                    "页面 2：单项日志 / 问题分析",
                    "  - 抓取当前日志：下拉框选到哪一项，就单独抓取哪一项；支持 Logcat、Crash、dmesg、4G、网络、设备属性、Activity。",
                    "  - 开始/暂停实时抓取：支持 Logcat、Crash、dmesg、4G/radio、网络轮询、Activity 相关日志；复现后暂停并自动分析。",
                    "  - 清除选中日志缓存：Logcat、Crash、dmesg、4G/radio 支持清除缓存；快照型日志没有缓存时会明确提示。",
                    "  - dmesg 日志：抓取内核日志，适合分析驱动、硬件、USB、底层网络问题；权限不足会红色提示原因和处理建议。",
                    "  - 4G / 蜂窝网络日志：抓取 radio 实时日志和 telephony、phone、carrier_config、mobile_data、getprop 快照，适合分析 SIM、APN、信号、移动数据。",
                    "  - 客户/FAE 提示：每个日志项显示客户看得懂的适用场景，以及 FAE 需要重点关注的字段和方向。",
                    "  - 简单分析：自动输出严重度、定位结论、证据、下一步建议，覆盖 crash、ANR、权限不足、超时、DNS/网络等问题。",
                    "",
                    "页面 3：功能说明与页面布局",
                    "  - 面向客户：告诉客户先点什么、哪里看结果、哪些失败可以忽略。",
                    "  - 面向 FAE：说明哪些按钮是工程师调试能力，哪些日志适合分析哪类问题。",
                    "",
                    "颜色规则",
                    "  - 绿色：成功或状态正常。",
                    "  - 黄色：正在运行、需要等待或需要客户确认。",
                    "  - 红色：失败、风险操作或需要处理的问题；界面会显示原因和解决建议。",
                    "",
                    "交付说明",
                    "  - 最终交付为单个 exe，内置 ADB，客户不需要安装 Python。",
                    "  - 所有耗时 ADB 操作都在后台执行，不弹黑色 CMD 窗口，不阻塞界面。",
                    "  - 投屏组件已内置在 exe 包内；如现场失败，优先检查设备授权、驱动、亮屏和 USB/网络连接。",
                ]
            )
        )
        layout.addWidget(text)
