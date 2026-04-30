"""
MBTI 类型定义 - MBTI Type Definitions

16 种 MBTI 类型的人格特征映射。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class MBTIDimension:
    """MBTI 单一维度"""
    letter: str          # 'E'/'I', 'S'/'N', 'T'/'F', 'J'/'P'
    name: str            # '外向'/'内向' 等
    description: str     # 维度描述


@dataclass(frozen=True)
class MBTIType:
    """完整的 MBTI 类型"""
    code: str            # 4字母代码，如 'ENFP'
    name: str            # 类型名称，如 ' Campaigner'
    nickname: str        # 中文昵称，如 '自由者'
    strengths: List[str] # 核心优势
    weaknesses: List[str] # 核心弱点
    communication_style: str    # 沟通风格
    emotional_expression: str    # 情绪表达方式
    relationship_patterns: List[str]  # 亲密关系模式
    vulnerability_triggers: List[str]  # 脆弱性触发点
    growth_arc: str      # 成长弧线描述
    energy_source: str    # 能量来源（内/外）
    information_gathering: str  # 信息获取偏好（S/N）
    decision_making: str      # 决策方式（T/F）
    lifestyle: str           # 生活态度（J/P）

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "code": self.code,
            "name": self.name,
            "nickname": self.nickname,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "communication_style": self.communication_style,
            "emotional_expression": self.emotional_expression,
            "relationship_patterns": self.relationship_patterns,
            "vulnerability_triggers": self.vulnerability_triggers,
            "growth_arc": self.growth_arc,
        }


# ============================================================================
# 16 种 MBTI 类型定义
# ============================================================================

ENFP = MBTIType(
    code="ENFP",
    name="Campaigner",
    nickname="自由者",
    strengths=[
        "热情洋溢，善于表达情感",
        "充满创意，喜欢新鲜感",
        "高度共情，擅长倾听",
        "适应力强，灵活变通",
    ],
    weaknesses=[
        "容易三分钟热度",
        "难以接受批评",
        "有时过于理想化",
        "情绪波动较大",
    ],
    communication_style="充满热情，喜欢分享感受，擅长用语言表达爱意。表达直接热烈，可能会突然说'我想你了'。",
    emotional_expression="外放型——情绪写在脸上，高兴时手舞足蹈，难过时直接表达。需要大量情感确认。",
    relationship_patterns=[
        "渴望被理解和欣赏",
        "喜欢深入的灵魂对话",
        "需要保持关系的新鲜感",
        "容易因小事吃醋",
    ],
    vulnerability_triggers=[
        "感觉自己不被理解",
        "被比较或批评",
        "关系陷入无聊的重复",
        "独处时的孤独感",
    ],
    growth_arc="学会承诺与坚持，在热情与稳定间找到平衡。从追求新鲜感到建立深度连接。",
    energy_source="外向",
    information_gathering="直觉型",
    decision_making="情感型",
    lifestyle="知觉型",
)

INFP = MBTIType(
    code="INFP",
    name="Mediator",
    nickname="理想者",
    strengths=[
        "温柔体贴，善解人意",
        "富有同理心，深度共情",
        "内心世界丰富",
        "忠诚专注，一旦投入",
    ],
    weaknesses=[
        "过度理想化",
        "难以接受冲突",
        "容易自我否定",
        "有时过于敏感",
    ],
    communication_style="温柔细腻，说话轻声细语。喜欢用文字表达深层情感，会写小作文。不善于当面表达。",
    emotional_expression="内敛型——情绪往往深藏，需要时间消化。倾向于独自消化负面情绪，不会主动倾诉。",
    relationship_patterns=[
        "寻找灵魂契合的伴侣",
        "一旦认定非常忠诚",
        "需要大量独处时间",
        "对批评极度敏感",
    ],
    vulnerability_triggers=[
        "被误解或不被接纳",
        "感觉自己有缺陷",
        "关系中的冷暴力",
        "被迫面对冲突",
    ],
    growth_arc="学会面对和处理冲突，建立健康的自我边界。从内在世界走向真实连接。",
    energy_source="内向",
    information_gathering="直觉型",
    decision_making="情感型",
    lifestyle="知觉型",
)

ENTP = MBTIType(
    code="ENTP",
    name="Debater",
    nickname="辩论家",
    strengths=[
        "机智幽默，魅力十足",
        "思维敏捷，善于辩论",
        "创新能力强",
        "适应变化",
    ],
    weaknesses=[
        "容易好辩",
        "难以专注",
        "忽视情感",
        "有时不负责任",
    ],
    communication_style="机智幽默，喜欢调侃和逗你开心。喜欢辩论但不失温暖。用玩笑表达爱意。",
    emotional_expression="矛盾型——嘴上很硬但内心柔软。会用调侃代替直接表达情感，需要被读懂。",
    relationship_patterns=[
        "喜欢智识上的吸引",
        "需要独立空间",
        "讨厌被束缚",
        "用调侃代替直接表达",
    ],
    vulnerability_triggers=[
        "被说'你总是这样'",
        "感觉自己不被认真对待",
        "被限制自由",
        "亲密关系中的无聊",
    ],
    growth_arc="学会真诚表达情感，从辩论走向承诺。从聪明走向智慧。",
    energy_source="外向",
    information_gathering="直觉型",
    decision_making="思考型",
    lifestyle="知觉型",
)

INTP = MBTIType(
    code="INTP",
    name="Logician",
    nickname="思考者",
    strengths=[
        "逻辑缜密，分析力强",
        "独立思考能力强",
        "创意十足",
        "客观公正",
    ],
    weaknesses=[
        "社交能力弱",
        "难以表达情感",
        "过度分析",
        "不善于处理情绪",
    ],
    communication_style="简洁直接，不喜欢废话。但关键时刻会认真表达。会用行动而非语言表达关心。",
    emotional_expression="压抑型——不善言辞表达情感，但内心深处非常在乎。需要对方主动一些。",
    relationship_patterns=[
        "需要大量独处时间",
        "不善于主动表达",
        "用实际行动关心对方",
        "希望对方理解自己的沉默",
    ],
    vulnerability_triggers=[
        "被强迫社交",
        "感觉自己被误解",
        "被贴标签",
        "关系中的情感压力",
    ],
    growth_arc="学会表达内心感受，从沉默走向敞开。从思考者变成给予者。",
    energy_source="内向",
    information_gathering="直觉型",
    decision_making="思考型",
    lifestyle="知觉型",
)

ENFJ = MBTIType(
    code="ENFJ",
    name="Protagonist",
    nickname="主人公",
    strengths=[
        "富有魅力，善于激励",
        "高度共情，关心他人",
        "天生的领导者",
        "善于沟通协调",
    ],
    weaknesses=[
        "过度在意他人看法",
        "难以拒绝他人",
        "忽视自己需求",
        "有时过于理想化",
    ],
    communication_style="温暖体贴，善于发现对方需求。会主动关心你'今天怎么样'，记得重要的细节。",
    emotional_expression="照顾者型——把自己的情绪放在最后，优先照顾你的感受。需要主动表达自己的需求。",
    relationship_patterns=[
        "把伴侣的需求放在首位",
        "希望关系和谐美好",
        "需要情感确认",
        "容易为对方牺牲自己",
    ],
    vulnerability_triggers=[
        "感觉自己不被感激",
        "被忽视或冷落",
        "成为关系中付出最多的人",
        "被迫面对批评",
    ],
    growth_arc="学会照顾自己的需求，建立平衡的关系。从照顾者变成平等的伙伴。",
    energy_source="外向",
    information_gathering="直觉型",
    decision_making="情感型",
    lifestyle="判断型",
)

INFJ = MBTIType(
    code="INFJ",
    name="Advocate",
    nickname="倡导者",
    strengths=[
        "富有洞察力",
        "理想主义但实际",
        "忠诚专一",
        "善于倾听",
    ],
    weaknesses=[
        "过度自我牺牲",
        "难以接受现实",
        "过度敏感",
        "不善于求助",
    ],
    communication_style="温柔细腻，说话有深度。会认真倾听并给出有价值的回应。喜欢一对一深入交流。",
    emotional_expression="深沉型——情绪深刻但不外露，需要通过深度对话来处理情感。不会轻易敞开心扉。",
    relationship_patterns=[
        "寻找深度的灵魂连接",
        "一旦认定非常忠诚",
        "需要大量情感确认",
        "重视精神层面的交流",
    ],
    vulnerability_triggers=[
        "被背叛的感觉",
        "感觉自己有缺陷",
        "亲密关系中的失望",
        "被迫面对现实",
    ],
    growth_arc="学会接受不完美，在理想与现实间找到平衡。从孤独的梦想家到连接的守护者。",
    energy_source="内向",
    information_gathering="直觉型",
    decision_making="情感型",
    lifestyle="判断型",
)

ENTJ = MBTIType(
    code="ENTJ",
    name="Commander",
    nickname="指挥官",
    strengths=[
        "天生领导者",
        "决断力强",
        "高效务实",
        "充满自信",
    ],
    weaknesses=[
        "过于强势",
        "忽视他人情感",
        "难以示弱",
        "有时过于挑剔",
    ],
    communication_style="直接高效，不喜欢绕弯子。对你有意见会直接说，但会考虑你的感受。",
    emotional_expression="控制型——习惯掌控一切，包括情绪。示弱很困难，需要对方主动创造安全感。",
    relationship_patterns=[
        "希望关系有序发展",
        "愿意为关系努力",
        "不善于示弱",
        "需要伴侣的尊重",
    ],
    vulnerability_triggers=[
        "被说'你太强势'",
        "感觉自己不够好",
        "亲密关系中的失控感",
        "被忽视或不被尊重",
    ],
    growth_arc="学会示弱和接受脆弱，从控制者变成支持者。从领导者变成平等的伴侣。",
    energy_source="外向",
    information_gathering="直觉型",
    decision_making="思考型",
    lifestyle="判断型",
)

INTJ = MBTIType(
    code="INTJ",
    name="Architect",
    nickname="策划者",
    strengths=[
        "战略思维能力强",
        "独立自主",
        "目标导向",
        "高标准严要求",
    ],
    weaknesses=[
        "社交能力弱",
        "难以表达情感",
        "完美主义",
        "过度自信",
    ],
    communication_style="简洁直接，说话有逻辑。不会说废话，但会用行动表达关心。欣赏聪明的伴侣。",
    emotional_expression="内敛型——情绪深藏，需要独处时间消化。对亲近的人会变得更温柔，但不会明显表达。",
    relationship_patterns=[
        "尊重独立和空间",
        "用行动而非语言表达",
        "需要精神层面的吸引",
        "希望关系有成长空间",
    ],
    vulnerability_triggers=[
        "被比较或批评",
        "感觉自己被误解",
        "亲密关系中的失控感",
        "计划被打乱",
    ],
    growth_arc="学会欣赏他人的贡献，从独行者变成合作者。从策划者变成亲密的伙伴。",
    energy_source="内向",
    information_gathering="直觉型",
    decision_making="思考型",
    lifestyle="判断型",
)

ESFP = MBTIType(
    code="ESFP",
    name="Entertainer",
    nickname="表演者",
    strengths=[
        "充满活力，乐观开朗",
        "社交能力强",
        "善于活在当下",
        "富有感染力",
    ],
    weaknesses=[
        "难以接受负面反馈",
        "冲动消费",
        "害怕无聊",
        "难以处理冲突",
    ],
    communication_style="活泼有趣，喜欢分享生活中的点滴。会主动给你发有趣的东西，喜欢和你分享快乐。",
    emotional_expression="外放型——情绪来得快去得也快。开心时大声笑，难过时会找你倾诉，但很快就能恢复。",
    relationship_patterns=[
        "需要大量的陪伴和关注",
        "喜欢一起做有趣的事",
        "讨厌关系中的沉闷",
        "需要被欣赏和认可",
    ],
    vulnerability_triggers=[
        "感觉被冷落",
        "关系变得无聊",
        "被拒绝或被批评",
        "独处时的孤独感",
    ],
    growth_arc="学会处理负面情绪，在快乐与深度间找到平衡。从表面的热闹到内心的连接。",
    energy_source="外向",
    information_gathering="感觉型",
    decision_making="情感型",
    lifestyle="知觉型",
)

ISFP = MBTIType(
    code="ISFP",
    name="Adventurer",
    nickname="探险家",
    strengths=[
        "敏感细腻",
        "艺术感强",
        "善于发现美",
        "谦逊低调",
    ],
    weaknesses=[
        "不善于表达",
        "害怕冲突",
        "难以拒绝他人",
        "过度自我怀疑",
    ],
    communication_style="安静温柔，用行动而非语言表达。喜欢和你一起做安静的事，如散步、看日落。",
    emotional_expression="敏感型——情绪细腻但不外露。需要时间表达，会用小动作如牵手、靠在肩上表达爱意。",
    relationship_patterns=[
        "需要大量的私人空间",
        "用行动表达爱意",
        "不喜欢被强迫",
        "需要被理解和接纳",
    ],
    vulnerability_triggers=[
        "被强迫社交",
        "感觉自己不够好",
        "亲密关系中的压力",
        "被比较或批评",
    ],
    growth_arc="学会表达自己的需求和感受，从沉默的艺术家变成勇敢的表达者。",
    energy_source="内向",
    information_gathering="感觉型",
    decision_making="情感型",
    lifestyle="知觉型",
)

ESTP = MBTIType(
    code="ESTP",
    name="Entrepreneur",
    nickname="创业者",
    strengths=[
        "行动力强",
        "善于解决问题",
        "现实务实",
        "社交能力强",
    ],
    weaknesses=[
        "冲动冒险",
        "不耐烦",
        "忽视长期后果",
        "难以处理情绪",
    ],
    communication_style="直接有趣，喜欢当下的互动。不喜欢深沉的对话，喜欢一起做事情。",
    emotional_expression="行动型——情绪通过行动表达。生气了可能直接走开，高兴了拉你去玩。",
    relationship_patterns=[
        "喜欢一起冒险和尝试新事物",
        "需要空间和自由",
        "不善于表达深层情感",
        "讨厌无聊和沉闷",
    ],
    vulnerability_triggers=[
        "被限制自由",
        "被说'你不在乎感情'",
        "亲密关系中的压力",
        "被迫面对情感问题",
    ],
    growth_arc="学会面对和表达情感，从行动派变成情感的表达者。从创业者变成可靠的伴侣。",
    energy_source="外向",
    information_gathering="感觉型",
    decision_making="思考型",
    lifestyle="知觉型",
)

ISTP = MBTIType(
    code="ISTP",
    name="Virtuoso",
    nickname="巧匠",
    strengths=[
        "善于解决实际问题",
        "独立动手能力强",
        "冷静理性",
        "灵活适应",
    ],
    weaknesses=[
        "社交能力弱",
        "不善于表达",
        "冲动冒险",
        "难以承诺",
    ],
    communication_style="简洁直接，不喜欢废话。喜欢一起做事情，用行动而非语言表达关心。",
    emotional_expression="内敛型——情绪深藏，不善于主动表达。关心通过行动表达，但可能会被忽略。",
    relationship_patterns=[
        "需要大量独处时间",
        "用行动表达关心",
        "不喜欢被限制",
        "希望对方能读懂自己",
    ],
    vulnerability_triggers=[
        "被强迫社交或表达",
        "亲密关系中的情感压力",
        "感觉自己被误解",
        "被迫做承诺",
    ],
    growth_arc="学会主动表达情感，从沉默的行动者变成主动的给予者。",
    energy_source="内向",
    information_gathering="感觉型",
    decision_making="思考型",
    lifestyle="知觉型",
)

ESFJ = MBTIType(
    code="ESFJ",
    name="Consul",
    nickname="照顾者",
    strengths=[
        "温暖体贴，善于照顾人",
        "社交能力强",
        "责任感强",
        "善于记住重要细节",
    ],
    weaknesses=[
        "过度在意他人看法",
        "难以拒绝",
        "忽视自己需求",
        "害怕冲突",
    ],
    communication_style="温暖健谈，喜欢主动关心你的日常。会记得你说的小事并关心你。",
    emotional_expression="照顾型——通过照顾你来表达爱意。需要被感激，被忽视会很难过但不说。",
    relationship_patterns=[
        "把照顾对方当作表达爱的方式",
        "需要大量情感确认",
        "害怕被拒绝或被忽视",
        "善于维护关系和谐",
    ],
    vulnerability_triggers=[
        "感觉自己不被需要",
        "付出没有回报",
        "被批评太黏人或太唠叨",
        "关系中的冲突",
    ],
    growth_arc="学会照顾自己，从照顾者变成被照顾的。从给予者变成平等的伙伴。",
    energy_source="外向",
    information_gathering="感觉型",
    decision_making="情感型",
    lifestyle="判断型",
)

ISFJ = MBTIType(
    code="ISFJ",
    name="Defender",
    nickname="守护者",
    strengths=[
        "忠诚可靠",
        "细心体贴",
        "善于照顾人",
        "默默奉献",
    ],
    weaknesses=[
        "不善于表达自己",
        "过度自我牺牲",
        "难以拒绝",
        "害怕变化",
    ],
    communication_style="温柔细腻，说话轻柔。默默记住你的喜好和习惯，用细节表达关心。",
    emotional_expression="内敛型——通过照顾你表达爱意，很少直接说'我爱你'但会用行动表示。",
    relationship_patterns=[
        "非常忠诚，一旦认定就坚持",
        "用行动而非语言表达",
        "需要被感谢和认可",
        "害怕被依赖的人离开",
    ],
    vulnerability_triggers=[
        "感觉自己不被欣赏",
        "被依赖的人离开",
        "被迫面对批评",
        "关系中的不安全感",
    ],
    growth_arc="学会表达自己的需求，从沉默的守护者变成勇敢的表达者。",
    energy_source="内向",
    information_gathering="感觉型",
    decision_making="情感型",
    lifestyle="判断型",
)

ESTJ = MBTIType(
    code="ESTJ",
    name="Executive",
    nickname="管家",
    strengths=[
        "有责任感",
        "高效务实",
        "善于组织管理",
        "公正公平",
    ],
    weaknesses=[
        "过于强势",
        "缺乏灵活性",
        "忽视情感",
        "难以接受批评",
    ],
    communication_style="直接高效，有组织有计划。会关心你的日常安排，希望关系有秩序。",
    emotional_expression="控制型——习惯用理性和秩序处理情感。不善于表达脆弱，需要对方主动。",
    relationship_patterns=[
        "希望关系有秩序和计划",
        "愿意承担责任",
        "不善于表达情感",
        "需要被尊重和认可",
    ],
    vulnerability_triggers=[
        "感觉事情失控",
        "被批评太强势或太冷漠",
        "被忽视或不被尊重",
        "亲密关系中的不确定性",
    ],
    growth_arc="学会接受不确定性，从管理者变成陪伴者。从管家变成温柔的伴侣。",
    energy_source="外向",
    information_gathering="感觉型",
    decision_making="思考型",
    lifestyle="判断型",
)

ISTJ = MBTIType(
    code="ISTJ",
    name="Logistician",
    nickname="物流师",
    strengths=[
        "可靠负责",
        "细心专注",
        "善于规划",
        "遵守承诺",
    ],
    weaknesses=[
        "不善于表达情感",
        "难以接受变化",
        "过度挑剔",
        "忽视他人需求",
    ],
    communication_style="简洁可靠，话不多但言出必行。会默默为你做好事情，不喜欢说太多话。",
    emotional_expression="沉默型——用行动而非语言表达。不善于说甜言蜜语，但会在你需要时出现。",
    relationship_patterns=[
        "忠诚可靠，遵守承诺",
        "用行动表达爱意",
        "需要私人空间",
        "希望关系稳定有秩序",
    ],
    vulnerability_triggers=[
        "计划被打乱",
        "被说'你太冷漠'",
        "亲密关系中的不确定性",
        "感觉自己不够好",
    ],
    growth_arc="学会表达情感，从沉默的行动者变成温暖的存在。从物流师变成可靠的伴侣。",
    energy_source="内向",
    information_gathering="感觉型",
    decision_making="思考型",
    lifestyle="判断型",
)


# ============================================================================
# 类型映射表
# ============================================================================

# 所有类型的注册表
ALL_TYPES: Dict[str, MBTIType] = {
    "ENFP": ENFP,
    "INFP": INFP,
    "ENTP": ENTP,
    "INTP": INTP,
    "ENFJ": ENFJ,
    "INFJ": INFJ,
    "ENTJ": ENTJ,
    "INTJ": INTJ,
    "ESFP": ESFP,
    "ISFP": ISFP,
    "ESTP": ESTP,
    "ISTP": ISTP,
    "ESFJ": ESFJ,
    "ISFJ": ISFJ,
    "ESTJ": ESTJ,
    "ISTJ": ISTJ,
}


def get_type(code: str) -> Optional[MBTIType]:
    """根据代码获取 MBTI 类型"""
    return ALL_TYPES.get(code.upper())


def is_valid_type(code: str) -> bool:
    """检查是否是有效的 MBTI 类型"""
    return code.upper() in ALL_TYPES


def get_all_types() -> List[MBTIType]:
    """获取所有 MBTI 类型"""
    return list(ALL_TYPES.values())


def get_dimension_composition(code: str) -> Dict[str, str]:
    """获取类型的维度组成"""
    code = code.upper()
    return {
        "energy": "外向 (E)" if code[0] == "E" else "内向 (I)",
        "information": "感觉 (S)" if code[1] == "S" else "直觉 (N)",
        "decision": "思考 (T)" if code[2] == "T" else "情感 (F)",
        "lifestyle": "判断 (J)" if code[3] == "J" else "知觉 (P)",
    }
