"""Сбор статистики репозитория: просмотры, клонирования, звёзды, форки, упоминания.

GitHub отдаёт трафик только за последние 14 дней, поэтому скрипт каждый день
дописывает дни в stats/traffic.json и пересчитывает итог в stats/summary.json.
Запускается из .github/workflows/traffic.yml. Токен — в секрете TRAFFIC_TOKEN
(fine-grained, этот репозиторий, Administration: read-only), в файлы не попадает.
"""
import datetime
import json
import os
import urllib.parse
import urllib.request

REPO = os.environ.get("REPO", "pavelnyuchev-droid/ai-project-method")
TOKEN = os.environ["TRAFFIC_TOKEN"]
STATS = os.path.join(os.path.dirname(__file__), "..", "stats")
# Что считаем упоминанием методики в чужих репозиториях
CITATION_QUERIES = ['"pavelnyuchev-droid/ai-project-method"', '"prostodelai.store/metodika"']


def api(path):
    req = urllib.request.Request(
        "https://api.github.com/" + path,
        headers={
            "Authorization": "Bearer " + TOKEN,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def load(name, default):
    path = os.path.join(STATS, name)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def save(name, data):
    os.makedirs(STATS, exist_ok=True)
    with open(os.path.join(STATS, name), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")


def merge_days(history, fresh):
    # По каждому дню берём максимум: за неполный текущий день GitHub досчитывает позже
    for day in fresh:
        key = day["timestamp"][:10]
        old = history.get(key, {"count": 0, "uniques": 0})
        history[key] = {
            "count": max(old["count"], day["count"]),
            "uniques": max(old["uniques"], day["uniques"]),
        }
    return history


def citations():
    found = {}
    for q in CITATION_QUERIES:
        res = api("search/code?per_page=100&q=" + urllib.parse.quote(q))
        for item in res.get("items", []):
            repo = item["repository"]["full_name"]
            if repo != REPO:
                found[repo] = item["repository"]["html_url"]
    return found


def main():
    traffic = load("traffic.json", {"views": {}, "clones": {}})
    traffic["views"] = merge_days(traffic["views"], api(f"repos/{REPO}/traffic/views")["views"])
    traffic["clones"] = merge_days(traffic["clones"], api(f"repos/{REPO}/traffic/clones")["clones"])
    save("traffic.json", traffic)

    repo = api(f"repos/{REPO}")
    refs = api(f"repos/{REPO}/traffic/popular/referrers")
    cited = citations()
    since = min(list(traffic["views"]) + list(traffic["clones"]) or [None])
    summary = {
        "updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "counting_since": since,
        "views_total": sum(d["count"] for d in traffic["views"].values()),
        "clones_total": sum(d["count"] for d in traffic["clones"].values()),
        "stars": repo["stargazers_count"],
        "forks": repo["forks_count"],
        "citations_github": len(cited),
        "citations_list": cited,
        "referrers_14d": [{"source": r["referrer"], "count": r["count"]} for r in refs],
    }
    save("summary.json", summary)
    # Значок для shields.io: https://img.shields.io/endpoint?url=<raw-ссылка на этот файл>
    save("badge-views.json", {
        "schemaVersion": 1,
        "label": "просмотры",
        "message": str(summary["views_total"]),
        "color": "blue",
    })


if __name__ == "__main__":
    main()
