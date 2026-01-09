# 初中数学 AI 辅导系统 (MathTutoring)

这是一个专为初中生设计的智能数学辅导系统，基于通义千问（Qwen）大模型开发。它不仅仅是一个问答机器人，更是一位能够运用**苏格拉底教学法**的“特级教师”，旨在通过启发式提问引导学生独立思考，而非直接给出答案。

## ✨ 核心功能

*   **🎓 启发式教学**：内置精心设计的 System Prompt，模拟资深数学老师的教学风格。针对概念题、计算题、应用题采用不同的引导策略。
*   **📐 LaTeX 公式渲染**：前端集成 [KaTeX](https://katex.org/)，后端强制 LaTeX 格式输出，完美展示复杂的数学公式（如 $\frac{-b \pm \sqrt{b^2-4ac}}{2a}$）。
*   **💬 交互体验优化**：
    *   支持 Markdown 格式解析。
    *   流式对话体验（模拟思考时间）。
    *   **反馈闭环**：每条回复支持“👍 有帮助”或“👎 没听懂”评价，数据自动记录用于后续优化。
*   **💾 数据持久化**：
    *   **客户端**：浏览器本地存储（LocalStorage）保留对话记录。
    *   **服务端**：自动记录所有对话日志 (`history.jsonl`) 和用户反馈 (`feedback.jsonl`)。
*   **🎨 现代 UI 设计**：清爽的亮色主题，适配移动端与桌面端，极简的操作界面。

## 🛠️ 技术栈

*   **前端**：原生 HTML5 / CSS3 / JavaScript (Vanilla JS)
    *   依赖库（CDN）：`marked.js` (Markdown解析), `KaTeX` (公式渲染)
*   **后端**：Python 3 (标准库 `http.server`)
    *   零依赖部署，无需 `pip install` 庞大的框架。
*   **模型服务**：阿里云 DashScope (通义千问)

## 🚀 快速开始

### 1. 环境准备
确保你的电脑已安装 Python 3.8 或以上版本。

### 2. 配置 API 密钥
在项目根目录下创建一个名为 `application.local.json` 的文件（该文件已被 `.gitignore` 忽略，保障安全），并填入你的 DashScope API Key：

```json
{
  "dashscope": {
    "api_key": "你的_API_KEY_粘贴在这里",
    "model": "qwen-turbo"
  },
  "server": {
    "port": 5173
  }
}
```

或者，你也可以通过环境变量配置：
*   `DASHSCOPE_API_KEY`
*   `QWEN_MODEL` (默认: `qwen-turbo`)

### 3. 启动服务
在终端运行以下命令：

```bash
python server.py
```

### 4. 开始辅导
打开浏览器访问：[http://localhost:5173](http://localhost:5173)

## 📂 项目结构

```
MathTutoring/
├── index.html              # 前端入口，包含 UI 逻辑与样式
├── server.py               # 后端服务，处理 API 请求与 Prompt 注入
├── application.local.json  # 配置文件 (需手动创建)
├── history.jsonl           # [自动生成] 服务端对话日志
├── feedback.jsonl          # [自动生成] 用户反馈日志
└── README.md               # 项目文档
```

## 🧠 教学策略配置

教学逻辑核心位于 `server.py` 中的 `DEFAULT_SYSTEM_PROMPT` 变量。目前的策略包括：

1.  **角色设定**：思维教练，拒绝做解题机器。
2.  **题型识别**：
    *   *概念题*：侧重对比与反例。
    *   *计算题*：侧重寻找易错点与关键步骤。
    *   *应用题*：**禁止直接列方程**，强制三步引导（已知量 -> 关系 -> 建模）。
3.  **防呆设计**：
    *   增加 `temperature` 参数至 0.7，提升回复的多样性。
    *   根据学生语气调整回应风格（鼓励/直接/幽默）。

## 📝 待办 / 改进计划

- [x] 接入 LaTeX 公式渲染
- [x] 实现用户反馈收集接口
- [x] 优化 System Prompt 避免机械化回复
- [ ] 添加多轮对话的上下文窗口限制（Token 优化）
- [ ] 增加语音输入/输出功能
