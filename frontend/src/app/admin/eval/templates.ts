export const DATASET_TEMPLATE_CSV = [
  "问题,答案,专业",
  "CPS0200 第一章范围讲的是什么？,描述本规范适用范围和对象,通用",
  "CPS0201 第一章范围的适用对象是什么？,回答规范面向的产品或工艺对象,通用",
].join("\n");

export const RETRIEVAL_TEMPLATE_JSONL = [
  JSON.stringify(
    {
      question: "CPS0200 第一章范围讲的是什么？",
      gold_chunk_ids: ["CPS0200_1"],
      gold_doc_ids: ["CPS0200"],
      domain: "通用",
      strategy: "parallel",
    },
    null,
    0,
  ),
  JSON.stringify(
    {
      question: "哪些规范文档包含工程图纸或大量图片分析内容？",
      gold_doc_ids: ["CPS1000"],
      domain: "图纸",
      strategy: "parallel",
    },
    null,
    0,
  ),
].join("\n");

export const RETRIEVAL_TEMPLATE_CSV = [
  "question,gold_chunk_ids,gold_doc_ids,domain,strategy",
  'CPS0200 第一章范围讲的是什么？,"CPS0200_1","CPS0200",通用,parallel',
  '哪些规范文档包含工程图纸或大量图片分析内容？,,"CPS1000",图纸,parallel',
].join("\n");
