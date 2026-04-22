# 我的研究方向 Profile

> LLM 每次运行会把本文件作为 system prompt 的一部分读入，用来做条目过滤与研究方向建议。
> 请用自然语言如实填写。越具体，建议越有针对性。

## 研究兴趣 / 主攻方向
- 大模型推理系统（inference engine）：TensorRT-LLM / vLLM / SGLang / LMDeploy 等
- 性能优化：KV Cache 管理、PagedAttention、speculative decoding、量化（W4A16/FP8）、MoE dispatch
- 分布式推理：TP / PP / EP、continuous batching、disaggregated prefill/decode
- CV模型/BERT模型等在新硬件上的优化方案，例如 Blackwell 上采用 FP8/FP4 推理BERT等

## 技术背景
- 熟悉 CUDA / Triton / C++，有 GPU kernel 开发经验
- 熟悉 PyTorch，了解 Transformer 架构细节

## 正在进行 / 近期关注
- 工业界先进的推理系统、推理方案，包括投机采样、多模态模型的量化/低精度推理优化、分布式 KVCache 优化
- 调研在 Blackwell 等新硬件上的推理部署路径以及预期成效
- 节约 tokens 的多轮对话方案，优化prompt的方法
- transformers 版本更新对 LLM 推理框架兼容性的影响

## 想避免的
- 与推理无关的 CV 话题
- 关联较弱的日常维护、版本管理、日志清理、CI等

## 关键词（会自动与 config.yaml 的 keywords 合并，粗筛标题/摘要）
keywords: LLM, inference, serving, KV cache, PagedAttention, speculative decoding, quantization, FP8, FP4, MoE, CUDA, Triton, TensorRT, vLLM, SGLang, LMDeploy, prefillonly, prefix-caching
