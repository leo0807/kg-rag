from src.services.entity_extractor import (
    _keep_process_name,
    _normalize_process_name,
    _postprocess_entity_item,
)


def test_keep_process_name_filters_meta_verbs():
    section = {"chunk_id": "CPS0100_5_3", "number": "5.3", "title": "胶嘴 nozzle", "content": "用于完成连接和设计。"}

    assert not _keep_process_name("完成", section)
    assert not _keep_process_name("连接", section)
    assert not _keep_process_name("引用", section)
    assert not _keep_process_name("经过培训并考核合格", section)
    assert not _keep_process_name("确认设备已完成清理工作", section)
    assert not _keep_process_name("处于正确的待机或关停状态", section)


def test_keep_process_name_keeps_real_actions():
    section = {"chunk_id": "CPS0100_6_1_8", "number": "6.1.8", "title": "技术要求", "content": "每次涂胶工作结束后，对点胶阀和管路进行彻底清洗。"}

    assert _keep_process_name("清洗", section)
    assert _keep_process_name("点胶", section)
    assert _keep_process_name("压力测试", section)


def test_postprocess_entity_item_filters_noise_relations():
    section = {"chunk_id": "CPS0100_5_4", "number": "5.4", "title": "供胶方式 feed system", "content": "系统用于实现供胶，入口接基料，出口接催化剂。"}
    item = {
        "chunk_id": "CPS0100_5_4",
        "tools": ["点胶阀", "无"],
        "materials": ["基料", "催化剂", "CPS1000"],
        "processes": ["实现供胶", "入口接", "混胶"],
        "relations": [
            {"from_type": "Process", "from_name": "实现供胶", "rel": "REQUIRES_TOOL", "to_type": "Tool", "to_name": "点胶阀"},
            {"from_type": "Process", "from_name": "混胶", "rel": "USES_MATERIAL", "to_type": "Material", "to_name": "基料"},
            {"from_type": "Process", "from_name": "入口接", "rel": "USES_MATERIAL", "to_type": "Material", "to_name": "催化剂"},
        ],
    }

    processed = _postprocess_entity_item(section, item)

    assert processed["tools"] == ["点胶阀"]
    assert processed["materials"] == ["基料", "催化剂"]
    assert processed["processes"] == ["混胶"]
    assert processed["relations"] == [
        {
            "from_type": "Process",
            "from_name": "混胶",
            "rel": "USES_MATERIAL",
            "to_type": "Material",
            "to_name": "基料",
        }
    ]


def test_normalize_process_name_compacts_sentence_style_names():
    assert _normalize_process_name("仔细检查产品") == "检查"
    assert _normalize_process_name("清理工作") == "清理"
    assert _normalize_process_name("机器人自动涂胶") == "自动涂胶"
