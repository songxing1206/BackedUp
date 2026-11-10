# Third-party notices

## CiteFact 0.3.0

Source: https://github.com/hearthresearch/citefact
仅复用现有 CiteFact 副本中的 `apa.py` 与 `base.py`，其余匹配、任务存储、HTTP 服务及界面自主实现。文件保留来源头；完整原许可证：`app/vendor/citefact/LICENSE`。

Copyright (c) 2026 José Fernandes. Licensed under the MIT License. 原许可中的版权及授权声明随文件保留。后续修改归本项目贡献者所有，不暗示原作者背书。

## Runtime dependencies

- pyparsing 3.3.3（bibtexparser 的依赖）：MIT，https://github.com/pyparsing/pyparsing
- pypdf: BSD-3-Clause，https://github.com/py-pdf/pypdf
- bibtexparser 1.4.4: BSD／LGPL 双许可，本分发选择其 COPYING 中的 BSD 条款，https://github.com/sciunto-org/python-bibtexparser

通过 Python 包依赖使用，未复制或修改依赖源码；分发依赖时应保留各自许可，并遵循其分发义务。当前版本不依赖 PyMuPDF。

## PDF coordinate extraction and preview

- pypdfium2: Apache-2.0 / BSD-3-Clause；https://github.com/pypdfium2-team/pypdfium2
- PDFium及其依赖：随pypdfium2二进制发布的各自许可与NOTICE，已从当前安装包复制到 `licenses/`。
- Pillow：HPND及组件各自许可；https://github.com/python-pillow/Pillow；安装包许可保留在 `licenses/`。

本地存储使用 platformdirs（MIT）。macOS 测试包包含 Python 运行时及 PyInstaller 引导程序（遵守其分发例外）；构建脚本额外收集打包依赖的 LICENSE／NOTICE 到 `licenses/`，包括 cryptography、cffi、pycparser、charset-normalizer。PyInstaller 仅用于构建；测试包不含构建环境或用户数据。

PDF文字/坐标提取与页面渲染调用现有库；片段ID、来源校验、逐行映射、任务状态与界面覆盖逻辑由本项目实现。没有复制或修改上述库源码。

## 自动审查提示词复用

复制 CiteFact 0.3.0 的 citefact/llm/prompts/claims_verdict_system.txt 到 app/vendor/citefact/prompts/claims_verdict_system.txt。原作者 © 2026 José Fernandes，MIT，完整许可证保留在 app/vendor/citefact/LICENSE。应用在原提示词后添加中文状态、逐源矩阵、真实片段/指纹校验与材料覆盖要求。没有复制训练模型权重；实际推理由用户连接的模型执行。


## 分发许可选择与呈现

本文件及 licenses/ 中的原始版权、条件、免责声明随源码和安装包提供；CiteFact 的完整 MIT 许可另保留于 app/vendor/citefact/LICENSE。界面的“开源许可”入口提供离线查看，不替代随软件携带的原文。中文适配说明仅为介绍，不修改原许可证或表示第三方作者背书。

- CiteFact、platformdirs、pyparsing、charset-normalizer：保留 MIT 版权、授权和免责声明全文。
- pypdf、bibtexparser（选择 BSD 分支）、cffi、pycparser：保留各自版权、再分发条件、免责声明与不得背书条件（如适用）。bibtexparser 的 COPYING 双许可原文完整保留，不将它错误标为仅 LGPL。
- pypdfium2：按其提供的 Apache-2.0／BSD-3-Clause 许可分发，保留完整许可及 PDFium 和附属组件的全部已随上游二进制提供的许可／通知。CC-BY-4.0 相关材料的原始归属和许可亦保留；不将该标记套用于整个产品。
- cryptography：保留其 Apache-2.0／BSD 双许可文本及相关通知。未修改依赖库源码。
- Pillow、Python：保留其随包提供的许可及包含的历史许可／第三方通知。
- PyInstaller 引导程序：保留 COPYING 和其中的 bootloader 分发例外；不声称整个产品因此采用 GPL。

CiteFact 文件的来源头和原始版权保留；Backed Up 的适配层及新增工作另行标识。依赖版本更新时重新核对实际文件，不能仅凭本表推断未来版本的许可。
