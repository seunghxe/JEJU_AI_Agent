"""Specific destinations must not be silently replaced by a district landmark."""
import re

# VisitJeju place details (contentsid), coordinates and road addresses.
PLACES = (
    ("델문도", ("델문도",), 33.54379, 126.668846, "제주시 조천읍 조함해안로 519-10", "CNTS_000000000001501"),
    ("봄날 카페", ("봄날카페", "카페봄날", "애월봄날"), 33.46246, 126.30959, "제주시 애월읍 애월로1길 25", "CNTS_000000000018337"),
    ("오는정김밥", ("오는정김밥",), 33.249676, 126.56757, "서귀포시 동문동로 2", "CNTS_000000000020123"),
)

def key(s):
    return re.sub(r"[^가-힣a-z0-9]", "", s.lower())

def local_shop(text):
    q = key(text)
    for name, aliases, lat, lon, addr, ref in PLACES:
        if any(a in q for a in aliases):
            return dict(name=name, lat=lat, lon=lon, address=addr, source="비짓제주", source_id=ref)

def shop_query(text):
    """Extract a short name for Local Search; retain the region for disambiguation."""
    explicit = re.match(r"^목적지\s*:\s*(.{1,80})$", text.strip())
    if explicit:
        return explicit[1].strip()
    # Use the text after the last explicit switch, not a negated old destination.
    text = re.split(r"(?:말고|대신)\s+(?=[가-힣])", text)[-1] if re.search(r"(?:말고|대신)\s+.+(?:카페|식당|김밥|델문도)", text) else text
    shop = local_shop(text)
    if shop:
        return shop["name"]
    # Strip the lead-in of '약속 장소를 ...로 바꿨어' before taking the place.
    body = re.split(r"(?:약속\s*장소|목적지|행선지)[를을는:]\s*", text)[-1]
    m = re.search(r"([가-힣A-Za-z0-9·-]{2,}(?:\s+[가-힣A-Za-z0-9·-]{1,16}){0,2}?\s*(?:카페|식당|해장국|국수|김밥|베이커리|커피숍))(?=에서|[에로을를은는]|\s|[.!?,]|$)", body)
    if m:
        phrase = m[1].strip()
        if not any(w in phrase for w in ("근처", "가까운", "새 카페", "아까", "가게 근방")):
            return phrase
    m = re.search(r"(?:^|\s)((?:함덕|애월|서귀포|제주시|성산|협재|한림|중문)\s+[가-힣A-Za-z0-9·-]{2,}?)(?:에서|에\s|으로\s|로\s|\s+근처)", body)
    if m and not re.search(r"(해수욕장|해변|공항|충전소|쪽|근처)$", m[1]):
        return m[1]
    changed = re.search(r"(?:약속\s*장소|목적지)[를을]\s+([^.!?]{2,45}?)(?:으로|로)\s*(?:바꿨|바꿔|바뀌|변경)", text)
    return changed[1].strip() if changed else None

def resolve_shop(text, lookup):
    shop = local_shop(text)
    if shop:
        return shop
    hit = lookup(text) if lookup else None
    if not hit:
        return None
    # A hit sharing only '함덕' or '카페' is not a business-name match.
    name = re.sub(r"^(?:제주특별자치도|제주시|제주|함덕|애월|서귀포|성산|협재|한림|중문)(?:읍|면|동|시)?\s+", "", text)
    core = re.sub(r"카페|식당|베이커리|커피숍", "", key(name))
    return hit if len(core) >= 2 and core in key(hit.get("name","")) else None
