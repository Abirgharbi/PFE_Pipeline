import json

b = r"datasets/07_delivery/st_ready/by_series/stm32cubef4/issues_json/st_ready_issues_stm32cubef4.json"
a = r"datasets/07_delivery/st_ready/by_series/stm32cubef4/issues_json/st_ready_issues_stm32cubef4_with_alfred_image_text.json"

with open(b, encoding="utf-8") as f:
    jb = json.load(f)
with open(a, encoding="utf-8") as f:
    ja = json.load(f)

mb = {x.get("issue_number"): x for x in jb.get("issues", [])}

for y in ja.get("issues", []):
    n = y.get("issue_number")
    if (y.get("image_analyses_count") or 0) <= 0:
        continue

    x = mb.get(n)
    if not x:
        continue

    t = x.get("st_ready_text", "")
    t2 = y.get("st_ready_text", "")
    if t == t2:
        continue

    print("issue", n)
    print("title", y.get("issue_title"))

    k = t.find("https://github.com/user-attachments")
    if k >= 0:
        before = t[max(0, k - 100):k + 260]
    else:
        before = t[:300]
    print("before", before.replace("\n", " "))

    j = t2.find("[IMAGE DESCRIPTION]")
    if j >= 0:
        after = t2[max(0, j - 100):j + 320]
    else:
        after = t2[:320]
    print("after", after.replace("\n", " "))

    ia = y.get("image_analyses") or []
    print("desc", ia[0].get("description", "")[:360] if ia else "")
    break
