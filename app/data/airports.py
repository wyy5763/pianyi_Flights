from app.core.models import Airport

AIRPORTS = [
    Airport("北京", "PEK", "北京首都国际机场"),
    Airport("上海", "PVG", "上海浦东国际机场"),
    Airport("广州", "CAN", "广州白云国际机场"),
    Airport("深圳", "SZX", "深圳宝安国际机场"),
    Airport("成都", "CTU", "成都天府/双流机场"),
    Airport("重庆", "CKG", "重庆江北国际机场"),
    Airport("西安", "XIY", "西安咸阳国际机场"),
    Airport("杭州", "HGH", "杭州萧山国际机场"),
    Airport("南京", "NKG", "南京禄口国际机场"),
    Airport("武汉", "WUH", "武汉天河国际机场"),
    Airport("长沙", "CSX", "长沙黄花国际机场"),
    Airport("郑州", "CGO", "郑州新郑国际机场"),
    Airport("青岛", "TAO", "青岛胶东国际机场"),
    Airport("厦门", "XMN", "厦门高崎国际机场"),
    Airport("大连", "DLC", "大连周水子国际机场"),
    Airport("沈阳", "SHE", "沈阳桃仙国际机场"),
    Airport("哈尔滨", "HRB", "哈尔滨太平国际机场"),
    Airport("长春", "CGQ", "长春龙嘉国际机场"),
    Airport("济南", "TNA", "济南遥墙国际机场"),
    Airport("昆明", "KMG", "昆明长水国际机场"),
    Airport("贵阳", "KWE", "贵阳龙洞堡国际机场"),
    Airport("海口", "HAK", "海口美兰国际机场"),
    Airport("三亚", "SYX", "三亚凤凰国际机场"),
    Airport("福州", "FOC", "福州长乐国际机场"),
    Airport("南宁", "NNG", "南宁吴圩国际机场"),
    Airport("乌鲁木齐", "URC", "乌鲁木齐地窝堡国际机场"),
    Airport("兰州", "LHW", "兰州中川国际机场"),
    Airport("太原", "TYN", "太原武宿国际机场"),
    Airport("石家庄", "SJW", "石家庄正定国际机场"),
    Airport("合肥", "HFE", "合肥新桥国际机场"),
    Airport("南昌", "KHN", "南昌昌北国际机场"),
    Airport("宁波", "NGB", "宁波栎社国际机场"),
]


def resolve_origin(value: str) -> Airport:
    value = value.strip()
    upper = value.upper()
    for airport in AIRPORTS:
        if value == airport.city or upper == airport.code:
            return airport
    raise ValueError(f"暂不支持出发城市：{value}")


def destinations_for(origin: Airport, limit: int) -> list[Airport]:
    return [a for a in AIRPORTS if a.code != origin.code][:limit]
