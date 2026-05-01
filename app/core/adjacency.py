"""
인접 역 그래프 모듈 (adjacency.py)
==================================

각 역의 인접 역 정보를 관리한다. 같은 노선에서 물리적으로 옆에 붙어있는
역들을 인접으로 정의한다.

[설계 철학]
- 인접 그래프를 데이터 파일이 아닌 코드로 정의: 발표·코드 리뷰 때
  "어떤 역이 인접인지" 한눈에 보이도록 함.
- 호선 확장이 쉬움: 새 노선의 역들과 그 인접 관계를 STATIONS, ADJACENCY
  딕셔너리에 추가하기만 하면 됨.

[중요 — 보고서에 명시할 정의]
"인접 역"이란 이 프로젝트에서 다음과 같이 정의된다:
  같은 노선에 속하면서, 물리적으로 한 정거장 거리에 있는 역.
환승역의 경우 한 노선만 고려한다 (단순화 가정).
"""

# 역 메타정보 (호선·기본 이용량·성격)
STATIONS = {
    "교대":       {"line": "2호선", "base": 12000, "type": "office"},
    "강남":       {"line": "2호선", "base": 25000, "type": "office"},
    "역삼":       {"line": "2호선", "base": 14000, "type": "office"},
    "선릉":       {"line": "2호선", "base": 13000, "type": "office"},
    "삼성":       {"line": "2호선", "base": 15000, "type": "office"},
    "합정":       {"line": "2호선", "base": 11000, "type": "leisure"},
    "홍대입구":   {"line": "2호선", "base": 22000, "type": "leisure"},
    "신촌":       {"line": "2호선", "base": 16000, "type": "leisure"},
    "이대":       {"line": "2호선", "base":  8000, "type": "leisure"},
    "잠실새내":   {"line": "2호선", "base": 10000, "type": "mixed"},
    "잠실":       {"line": "2호선", "base": 20000, "type": "mixed"},
    "잠실나루":   {"line": "2호선", "base":  8000, "type": "mixed"},
    "강변":       {"line": "2호선", "base": 14000, "type": "mixed"},
    "시청":       {"line": "2호선", "base": 13000, "type": "office"},
    "을지로입구": {"line": "2호선", "base": 12000, "type": "office"},
}

# 양방향 인접 관계
ADJACENCY = {
    "교대":       ["강남"],
    "강남":       ["교대", "역삼"],
    "역삼":       ["강남", "선릉"],
    "선릉":       ["역삼", "삼성"],
    "삼성":       ["선릉"],
    "합정":       ["홍대입구"],
    "홍대입구":   ["합정", "신촌"],
    "신촌":       ["홍대입구", "이대"],
    "이대":       ["신촌"],
    "잠실새내":   ["잠실"],
    "잠실":       ["잠실새내", "잠실나루"],
    "잠실나루":   ["잠실", "강변"],
    "강변":       ["잠실나루"],
    "시청":       ["을지로입구"],
    "을지로입구": ["시청"],
}


def get_neighbors(station: str) -> list:
    """주어진 역의 인접 역 리스트를 반환. 없으면 빈 리스트."""
    return ADJACENCY.get(station, [])


def get_line(station: str) -> str:
    """역이 속한 노선 이름. 없으면 빈 문자열."""
    info = STATIONS.get(station, {})
    return info.get("line", "")


def get_all_stations() -> list:
    """등록된 모든 역 이름 리스트 (사전 순)"""
    return sorted(STATIONS.keys())


def get_stations_on_line(line: str) -> list:
    """같은 노선의 모든 역"""
    return [s for s, info in STATIONS.items() if info["line"] == line]


def is_neighbor(a: str, b: str) -> bool:
    """두 역이 인접인지"""
    return b in ADJACENCY.get(a, [])


def validate_graph() -> bool:
    """
    인접 그래프의 일관성을 검사한다.
    A의 인접 리스트에 B가 있으면, B의 인접 리스트에도 A가 있어야 한다.
    (양방향성)
    """
    for a, neighbors in ADJACENCY.items():
        for b in neighbors:
            if a not in ADJACENCY.get(b, []):
                print(f"[경고] 비대칭 인접: {a}->{b} 있음, {b}->{a} 없음")
                return False
    return True


if __name__ == "__main__":
    print(f"등록된 역 수: {len(STATIONS)}")
    print(f"인접 그래프 일관성: {'OK' if validate_graph() else 'FAIL'}")
    print(f"\n강남역의 인접 역: {get_neighbors('강남')}")
    print(f"홍대입구의 인접 역: {get_neighbors('홍대입구')}")
    print(f"\n시청역과 강남역은 인접? {is_neighbor('시청', '강남')}")
    print(f"강남역과 역삼역은 인접? {is_neighbor('강남', '역삼')}")
