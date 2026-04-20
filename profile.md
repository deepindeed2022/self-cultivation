# 我的研究方向 Profile

> LLM 每次运行会把本文件作为 system prompt 的一部分读入，用来做条目过滤与研究方向建议。
> 请用自然语言如实填写。越具体，建议越有针对性。

## 研究兴趣 / 主攻方向
- 大模型推理系统（inference engine）：TensorRT-LLM / vLLM / SGLang / LMDeploy 等
- 性能优化：KV Cache 管理、PagedAttention、speculative decoding、量化（W4A16/FP8）、MoE dispatch
- 分布式推理：TP / PP / EP、continuous batching、disaggregated prefill/decode

## 技术背景
- 熟悉 CUDA / Triton / C++，有 GPU kernel 开发经验
- 熟悉 PyTorch，了解 Transformer 架构细节

## 正在进行 / 近期关注
- 例如：「给 vLLM 加一个 xxx feature」「调研 Blackwell 上 FP4 推理路径」

## 想避免的
- 纯理论论文（无工程落地参考）、与推理无关的 CV 话题

## 关键词（会自动与 config.yaml 的 keywords 合并，粗筛标题/摘要）
keywords: LLM, inference, serving, KV cache, PagedAttention, speculative decoding, quantization, FP8, FP4, MoE, CUDA, Triton, TensorRT, vLLM, SGLang, LMDeploy
