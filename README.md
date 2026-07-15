# ProjectQuickStar

企业级源码智能分析平台。当前支持 PyQt6 GUI、目录/压缩包导入、并发项目扫描、语言检测、文件职责与代码符号解析、Markdown/HTML 报告，以及任务暂停、继续和取消。

当你进入一家新公司、不熟悉项目代码构成和现有文档时，可以通过本工具快速了解项目业务与代码组成。

## 运行

```powershell
python -m pip install -r requirements.txt
python main.py
```

请确保安装依赖和运行程序使用的是同一个 Python 解释器。在 PyCharm 中，
二者都应使用项目设置中选择的解释器。

支持本地目录、ZIP、TAR、TAR.GZ、TGZ；RAR 需要系统中存在 `unrar`、`unar` 或 7-Zip 等 `rarfile` 可调用的后端。

每次分析完成会自动生成：

- `output/project_analysis.md`
- `output/project_analysis.html`

## 测试

```powershell
python -m unittest discover -s tests -v
```
