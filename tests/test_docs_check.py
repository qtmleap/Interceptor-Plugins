"""The documentation checker must accept a coherent built site and reject each class of defect."""
import json
import subprocess
import sys

from helpers import Case, REPO

PAGES = ("index", "what-is-interceptor", "getting-started", "authoring", "api", "examples", "publishing", "devcontainer")


def html(lang, body="", head=""):
    return f'<!doctype html><html lang="{lang}"><head>{head}</head><body>{body}</body></html>'


class CheckDocsTests(Case):
    def fixture(self, base="/plugins/"):
        root = self.make_root()
        for directory in ("src", "types", "manifests", "fixtures"):
            (root / directory).mkdir(exist_ok=True)
        (root / "src/a.ts").write_text("x")
        website = root / "website"
        for locale in ("", "en"):
            (website / locale).mkdir(parents=True, exist_ok=True)
            for slug in PAGES:
                (website / locale / f"{slug}.md").write_text("# Title\n")
        site = root / "build/docs"
        (site / "assets").mkdir(parents=True)
        (site / "assets/app.js").write_text("1")
        (site / "assets/chunks").mkdir()
        for locale in ("root", "en"):
            (site / "assets/chunks" / f"@localSearchIndex{locale}.abc.js").write_text("export default '{}'")
        (site / "404.html").write_text(html("ja"))
        for directory, lang in (("", "ja"), ("en/", "en")):
            (site / directory).mkdir(exist_ok=True)
            for slug in PAGES:
                body = f'<a href="{base}{directory}api#heading">api</a><h2 id="heading">h</h2>'
                (site / f"{directory}{slug}.html").write_text(html(lang, body, f'<script src="{base}assets/app.js"></script>'))
        context = {"name": "Plugins", "repositoryURL": "https://example.com/plugins/repository.json", "base": base,
                   "githubRepository": "o/n", "fingerprint": None, "bunVersion": "1.3.6"}
        (root / "build").mkdir(exist_ok=True)
        (root / "build/docs-context.json").write_text(json.dumps(context))
        return root, site

    def check(self, root, site):
        return subprocess.run([sys.executable, str(REPO / "tools/check_docs.py"), "--root", str(root), "--site", str(site)],
                              capture_output=True, text=True, timeout=60)

    def rejects(self, root, site, fragment):
        proc = self.check(root, site)
        self.fails(proc)
        self.assertIn(fragment, proc.stdout)

    def test_accepts_a_coherent_site(self):
        root, site = self.fixture()
        self.ok(self.check(root, site))

    def test_rejects_missing_locale_page_in_source_and_site(self):
        root, site = self.fixture()
        (root / "website/en/api.md").unlink()
        self.rejects(root, site, "missing page api")
        root, site = self.fixture()
        (site / "en/api.html").unlink()
        self.rejects(root, site, "en/api.html")

    def test_rejects_wrong_language_attribute(self):
        root, site = self.fixture()
        (site / "en/index.html").write_text(html("ja"))
        self.rejects(root, site, "lang")

    def test_rejects_broken_link_anchor_and_asset(self):
        root, site = self.fixture()
        (site / "api.html").write_text(html("ja", '<a href="/plugins/nope">x</a>'))
        self.rejects(root, site, "broken link")
        root, site = self.fixture()
        (site / "api.html").write_text(html("ja", '<a href="/plugins/api#missing">x</a><h2 id="other"></h2>'))
        self.rejects(root, site, "missing anchor")
        root, site = self.fixture()
        (site / "api.html").write_text(html("ja", "", '<script src="/plugins/assets/gone.js"></script>'))
        self.rejects(root, site, "broken asset")
        root, site = self.fixture()
        (site / "api.html").write_text(html("ja", '<a href="/elsewhere">x</a>'))
        self.rejects(root, site, "outside the site base")

    def test_rejects_missing_search_index_unresolved_tokens_and_unpublishable_files(self):
        root, site = self.fixture()
        next(site.glob("assets/chunks/*localSearchIndexen*")).unlink()
        self.rejects(root, site, "search index")
        root, site = self.fixture()
        (site / "api.html").write_text(html("ja", "%%FINGERPRINT%%"))
        self.rejects(root, site, "token")
        for name in ("README.md", ".env", "build.py"):
            root, site = self.fixture()
            (site / name).write_text("x")
            self.rejects(root, site, name)

    def test_rejects_includes_outside_canonical_sources(self):
        root, site = self.fixture()
        (root / "website/api.md").write_text("<<< @/../tools/guard.py\n")
        self.rejects(root, site, "include")
        root, site = self.fixture()
        (root / "website/api.md").write_text("<<< @/../src/missing.ts\n")
        self.rejects(root, site, "does not exist")
        root, site = self.fixture()
        (root / "website/api.md").write_text("<<< @/../src/a.ts{1}\n```\n<<< @/../tools/x\n```\n")
        self.ok(self.check(root, site))

    def test_custom_repository_site_must_not_carry_official_identity(self):
        root, site = self.fixture()
        (site / "api.html").write_text(html("ja", "https://qtmleap.github.io/Interceptor-Plugins/"))
        self.rejects(root, site, "official identity")

    def test_checks_indented_snippets_ranges_and_html_includes_inside_fences(self):
        for snippet in ("   <<< @/../tools/guard.py{1,2 py}",
                        "<<< @/../tools/guard.py{malformed",
                        "```ts\n<!-- @include: @/../tools/guard.py -->\n```"):
            root, site = self.fixture()
            (root / "website/api.md").write_text(snippet + "\n")
            self.rejects(root, site, "include")
        root, site = self.fixture()
        (root / "website/api.md").write_text("   <<< @/../src/a.ts{1,2 ts}\n")
        self.ok(self.check(root, site))

    def test_frontmatter_repository_name_is_literal_in_nested_html_fields(self):
        name = '<img src=x onerror=alert(1)> {{7*7}} & "tea"'
        context = {"name": name, "repositoryURL": "https://example.com/repository.json",
                   "githubRepository": "o/n", "fingerprint": None, "bunVersion": "1.3.6", "base": "/"}
        script = ('import {substituteFrontmatter} from "./website/.vitepress/tokens.mts";'
                  'console.log(JSON.stringify(substituteFrontmatter('
                  '{title:"%%REPOSITORY_NAME%%", features:[{title:"%%REPOSITORY_NAME%%",details:"%%REPOSITORY_NAME%%"}]},'
                  + json.dumps(context) + ',{unconfigured:"Unset"})));')
        proc = subprocess.run(["bun", "--eval", script], cwd=REPO, capture_output=True, text=True, timeout=60)
        self.ok(proc)
        result = json.loads(proc.stdout)
        self.assertEqual(result["title"], name)
        from html import unescape
        for field in ("title", "details"):
            value = result["features"][0][field]
            self.assertNotIn("<img", value)
            self.assertNotIn("{{", value)
            self.assertEqual(unescape(value), name)

    def test_literal_name_in_serialized_script_is_not_html_injection(self):
        root, site = self.fixture()
        p = root / "build/docs-context.json"
        context = json.loads(p.read_text())
        context["name"] = "Tea & biscuits"
        p.write_text(json.dumps(context))
        (site / "api.html").write_text(html("ja", '<h2 id="heading">Tea &amp; biscuits</h2><script>const name="Tea & biscuits";</script>'))
        (site / "assets/app.js").write_text('const name="Tea & biscuits";')
        self.ok(self.check(root, site))
