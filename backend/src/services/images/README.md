# services/images — 图片提取与视觉分析

## 文件地图
| 文件 | 职责 |
|------|------|
| `pdf_image_extractor.py` | 从 PDF 页面提取嵌入图片（pdfplumber/fitz） |
| `docx_image_extractor.py` | 从 DOCX 中提取图片（python-docx） |
| `image_analyzer.py` | 图片内容分析调度：OCR / 图表识别 / 技术图纸 |
| `vision_service.py` | 调用视觉 API（OpenAI vision / 本地 VLM） |
| `vision_api_providers.py` | 云端视觉服务提供商适配（OpenAI / Azure） |
| `vision_local_providers.py` | 本地视觉模型适配（LLaVA / Qwen-VL） |
| `vision_support.py` | 提示词模板、结果解析辅助 |
| `image_vector_service.py` | 图片向量化并写入 Milvus |
| `image_file_service.py` | 图片文件存储（本地 / OSS） |
| `image_utils.py` | 图片压缩、格式转换、base64 编解码 |
| `drawing_analyzer.py` | 工程图纸专项分析（零件图、装配图） |
| `formula_service.py` | 图片中的公式识别（LaTeX 输出） |
| `multimodal_writer.py` | 将图片分析结果写入 Neo4j 节点 |
| `query_image_context.py` | 检索时关联图片上下文 |

## 核心流程
```
PDF 上传 → pdf_image_extractor → 图片列表
  → image_analyzer → vision_service（云/本地）→ 描述文本
  → image_vector_service → Milvus（向量）
  → multimodal_writer → Neo4j（关系）
```

## 注意事项
- 默认使用 OpenAI vision，切换本地模型需设置 `VISION_PROVIDER=local`
- 图片超过 4MB 会自动压缩至 2MB（`image_utils.compress`）
- formula_service 依赖 pix2tex，未安装时跳过公式识别

## 测试
```bash
pytest tests/test_pdf_image_extractor.py tests/test_image_vector_service.py -v
```
