"""无需真实 Chroma/网络的结构化过滤单元测试。"""
from __future__ import annotations
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

@dataclass
class Document:
    page_content: str
    metadata: dict

from query_rag import QueryFilters, answer_question, document_matches_filters, parse_query_filters, retrieve


def movie(title, year, genre, country, rating, votes):
    return Document(title, {"title": title, "year": year, "genres": genre, "country": country,
                            "rating": rating, "votes": votes, "director": "测试导演",
                            "gross_usd": -1, "crawl_date": "2026-09-08"})


class FakeStore:
    def __init__(self, items): self.items, self.ks = items, []
    def similarity_search_with_relevance_scores(self, question, k): self.ks.append(k); return self.items[:k]
    def similarity_search(self, question, k): self.ks.append(k); return [doc for doc, _ in self.items[:k]]


class FullStore(FakeStore):
    def get(self, include=None):
        docs = [doc for doc, _ in self.items]
        return {
            "documents": [doc.page_content for doc in docs],
            "metadatas": [doc.metadata for doc in docs],
        }


class FilterTests(unittest.TestCase):
    def test_parse_combined_constraints(self):
        f = parse_query_filters("推荐几部90年代高分国产喜剧电影")
        self.assertEqual((f.min_rating, f.genres, f.countries, f.year_min, f.year_max), (7.0, ("喜剧",), ("中国",), 1990, 1999))
        f = parse_query_filters("找2010到2020年8.5分以上的美国科幻动作片")
        self.assertEqual((f.min_rating, f.genres, f.countries, f.year_min, f.year_max), (8.5, ("动作", "科幻"), ("美国",), 2010, 2020))

    def test_all_required_genres_countries_and_year_forms(self):
        for value in ("喜剧", "动作", "科幻", "剧情", "恐怖", "爱情", "动画", "冒险", "犯罪", "悬疑"):
            self.assertIn(value, parse_query_filters(f"推荐{value}电影").genres)
        for value in ("中国", "美国", "日本", "韩国", "英国", "法国", "印度"):
            self.assertIn(value, parse_query_filters(f"推荐{value}电影").countries)
        self.assertEqual(parse_query_filters("国产电影").countries, ("中国",))
        exact = parse_query_filters("2018年的电影")
        self.assertEqual((exact.year_min, exact.year_max), (2018, 2018))
        self.assertEqual(parse_query_filters("2015年以后的电影").year_min, 2015)
        self.assertEqual(parse_query_filters("2000年以前的电影").year_max, 2000)

    def test_filter_expand_rerank_dedupe_and_output(self):
        low = movie("低分", 2019, "喜剧/Comedy", "中国/China", 6.2, 900000)
        high = movie("高分", 2018, "喜剧/Comedy", "中国/China", 8.8, 500000)
        duplicate = movie("高分", 2018, "喜剧/Comedy", "中国/China", 8.8, 500000)
        foreign = movie("外国", 2018, "喜剧/Comedy", "美国/United States", 9.0, 800000)
        store = FakeStore([(low, .99), (high, .80), (duplicate, .79), (foreign, .95)])
        docs = retrieve(store, "推荐2010到2020年8分以上国产喜剧", 3)
        self.assertEqual([d.metadata["title"] for d in docs], ["高分"])
        self.assertGreaterEqual(store.ks[0], 100)
        output = answer_question(FakeStore([(high, .8)]), "推荐高分国产喜剧", 1, False)
        for text in ("已应用筛选", "评分 ≥ 7.0", "类型：喜剧", "国家/地区：中国", "《高分》"):
            self.assertIn(text, output)

    def test_match_ranking_and_unfiltered_semantic_order(self):
        filters = QueryFilters(8.0, ("喜剧",), ("中国",), 2010, 2020)
        good = movie("符合", 2018, "喜剧/Comedy", "中国/China", 8.8, 500000)
        self.assertTrue(document_matches_filters(good, filters))
        self.assertFalse(document_matches_filters(movie("低分", 2018, "喜剧/Comedy", "中国/China", 6, 10), filters))
        close = movie("相关", 2020, "科幻/Sci-Fi", "美国/United States", 7.1, 100)
        strong = movie("优质", 2020, "科幻/Sci-Fi", "美国/United States", 9.2, 1000000)
        self.assertEqual(retrieve(FakeStore([(close, .9), (strong, .8)]), "高分美国科幻电影", 2)[0].metadata["title"], "优质")
        self.assertEqual([d.metadata["title"] for d in retrieve(FakeStore([(close, .9), (strong, .8)]), "周末看什么", 2)], ["相关", "优质"])

    def test_global_sort_intents(self):
        cheap = movie("普通票房", 2018, "动作/Action", "美国/United States", 9.0, 900000)
        rich = movie("票房冠军", 2015, "动作/Action", "美国/United States", 7.2, 200000)
        cheap.metadata["gross_usd"] = 10_000_000
        rich.metadata["gross_usd"] = 900_000_000
        store = FullStore([(cheap, .99), (rich, .20)])
        filters = parse_query_filters("哪些动作电影的全球票房最高")
        self.assertEqual(filters.sort_by, "gross")
        self.assertEqual(retrieve(store, "哪些动作电影的全球票房最高", 2)[0].metadata["title"], "票房冠军")
        self.assertEqual(parse_query_filters("最新的科幻电影").sort_by, "year")
        self.assertEqual(parse_query_filters("评分最高的喜剧电影").sort_by, "rating")


if __name__ == "__main__": unittest.main()
