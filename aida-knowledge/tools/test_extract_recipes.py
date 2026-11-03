import tempfile
import unittest
from pathlib import Path

from extract_recipes import RecipeError, load_recipes, parse_recipes

CARD = """# Title

```python
# RECIPE NET-FUNNEL v1.0 | Skill: 5.9 Network | Risk: R1
# Registry: NET.FUNNEL | Input: transactions(from_acct, to_acct, amount, ts)
def net_funnel(tables: dict, cfg: dict) -> pd.DataFrame:
    tx = tables["transactions"]
    n = len(tx)
    out = pd.DataFrame({"n": [n]})
    return out
```
"""

CARD_A = """```python
# RECIPE CORE-HELPER v1.0 | Skill: 1.1 Core | Risk: -
# Registry: - | Input: transactions(amount)
def helper(x):
    return x * 2

def core_helper(tables: dict, cfg: dict) -> pd.DataFrame:
    return pd.DataFrame()
```
"""

CARD_B = """```python
# RECIPE USE-HELPER v1.0 | Skill: 1.1 Core | Risk: -
# Registry: - | Input: transactions(amount)
def use_helper(tables: dict, cfg: dict) -> pd.DataFrame:
    return pd.DataFrame({"v": [helper(21)]})
```
"""


def write(text):
    d = tempfile.mkdtemp()
    p = Path(d) / "cards.md"
    p.write_text(text, encoding="utf-8")
    return p


class ExtractRecipesTest(unittest.TestCase):
    def test_parse_header_fields(self):
        r = parse_recipes(CARD)[0]
        self.assertEqual(r.id, "NET-FUNNEL")
        self.assertEqual(r.version, "1.0")
        self.assertEqual(r.skill, "5.9 Network")
        self.assertEqual(r.risk, "R1")
        self.assertEqual(r.registry_keys, ["NET.FUNNEL"])
        self.assertEqual(r.func_name, "net_funnel")
        self.assertTrue(r.inputs.startswith("transactions("))

    def test_load_defines_function(self):
        fns = load_recipes([write(CARD)])
        out = fns["net_funnel"]({"transactions": [1, 2, 3]}, {})
        self.assertEqual(int(out["n"][0]), 3)

    def test_truncated_recipe_raises(self):
        lines = CARD.splitlines()
        cut = "\n".join(lines[: len(lines) // 2 + 1])
        with self.assertRaises(RecipeError) as cm:
            load_recipes([write(cut)])
        self.assertIn("NET-FUNNEL", str(cm.exception))

    def test_truncated_inside_expression_raises(self):
        bad = CARD.replace('out = pd.DataFrame({"n": [n]})', 'out = pd.DataFrame({"n": [n')
        with self.assertRaises(RecipeError) as cm:
            load_recipes([write(bad)])
        self.assertIn("NET-FUNNEL", str(cm.exception))

    def test_missing_function_raises(self):
        bad = CARD.replace("def net_funnel(", "def other_name(")
        with self.assertRaises(RecipeError) as cm:
            load_recipes([write(bad)])
        self.assertIn("net_funnel", str(cm.exception))

    def test_shared_namespace(self):
        fns = load_recipes([write(CARD_A + "\n" + CARD_B)])
        out = fns["use_helper"]({}, {})
        self.assertEqual(int(out["v"][0]), 42)

    def test_non_recipe_python_block_ignored(self):
        md = "```python\nprint('x')\n```\n" + CARD
        self.assertEqual([r.id for r in parse_recipes(md)], ["NET-FUNNEL"])


class SpikeKitTest(unittest.TestCase):
    def test_spike_card_flags_only_f01(self):
        import pandas as pd
        spike = Path(__file__).resolve().parent.parent / "spike"
        fns = load_recipes([spike / "AIDA-SPIKE-recipes.md"])
        tx = pd.read_csv(spike / "spike-transactions.csv")
        self.assertEqual(len(tx), 200)
        cfg = {"NET.FUNNEL": {"min_sources": 10, "out_ratio": 0.8, "days": 7}}
        out = fns["net_funnel"]({"transactions": tx}, cfg)
        self.assertEqual(out["acct"].tolist(), ["F01"])

    def test_spike_template_has_end_marker(self):
        spike = Path(__file__).resolve().parent.parent / "spike"
        text = (spike / "AIDA-SPIKE-recipes.md").read_text(encoding="utf-8")
        self.assertIn("<!-- END-OF-TEMPLATE -->", text)
        self.assertNotIn("http://", text.split("```html")[1])
        self.assertNotIn("https://", text.split("```html")[1])


if __name__ == "__main__":
    unittest.main()
