import sys
import unittest

from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from app import main


class ArticleExtractionTests(unittest.TestCase):
    def test_prefers_og_title_and_article_body(self):
        html = """
        <html>
          <head>
            <title>Fallback Site Title</title>
            <meta
              property="og:title"
              content="Arsenal complete major signing"
            >
          </head>
          <body>
            <nav>
              Transfer News Fixtures Results
            </nav>

            <article>
              <h1>Different visible heading</h1>

              <p>
                Arsenal have completed the signing
                after several weeks of negotiations.
              </p>

              <p>
                The player has agreed a long-term
                contract with the club.
              </p>
            </article>

            <footer>
              Privacy Cookies Contact
            </footer>
          </body>
        </html>
        """

        result = main.extract_article_content(
            html
        )

        self.assertEqual(
            result["title"],
            "Arsenal complete major signing",
        )

        self.assertIn(
            "several weeks of negotiations",
            result["text"],
        )

        self.assertIn(
            "long-term contract",
            result["text"],
        )

        self.assertNotIn(
            "Transfer News Fixtures Results",
            result["text"],
        )

        self.assertNotIn(
            "Privacy Cookies Contact",
            result["text"],
        )

        self.assertEqual(
            result["extraction_method"],
            "article",
        )

        self.assertEqual(
            result["paragraph_count"],
            2,
        )

    def test_falls_back_to_h1_and_main(self):
        html = """
        <html>
          <body>
            <header>
              Site navigation and account controls
            </header>

            <main>
              <h1>
                Championship race enters final round
              </h1>

              <p>
                The leading teams remain separated
                by only a small number of points.
              </p>

              <p>
                Sunday will determine the final
                standings after a dramatic season.
              </p>
            </main>
          </body>
        </html>
        """

        result = main.extract_article_content(
            html
        )

        self.assertEqual(
            result["title"],
            "Championship race enters final round",
        )

        self.assertEqual(
            result["extraction_method"],
            "main",
        )

        self.assertNotIn(
            "account controls",
            result["text"],
        )

    def test_falls_back_to_document_title(self):
        html = """
        <html>
          <head>
            <title>
              Driver confirms future &amp; new deal
            </title>
          </head>
          <body>
            <article>
              <p>
                The driver confirmed that a new
                agreement has now been signed.
              </p>

              <p>
                Further details are expected before
                the next race weekend begins.
              </p>
            </article>
          </body>
        </html>
        """

        result = main.extract_article_content(
            html
        )

        self.assertEqual(
            result["title"],
            "Driver confirms future & new deal",
        )

    def test_removes_scripts_styles_and_asides(self):
        html = """
        <html>
          <head>
            <meta
              name="twitter:title"
              content="Club announces coaching change"
            >

            <style>
              body { display: none; }
            </style>

            <script>
              window.secretTrackingValue = 123;
            </script>
          </head>
          <body>
            <article>
              <aside>
                Subscribe to our newsletter now.
              </aside>

              <p>
                The club announced a coaching change
                following its latest league match.
              </p>

              <p>
                An interim appointment will take
                charge while the search continues.
              </p>
            </article>
          </body>
        </html>
        """

        result = main.extract_article_content(
            html
        )

        self.assertEqual(
            result["title"],
            "Club announces coaching change",
        )

        self.assertNotIn(
            "secretTrackingValue",
            result["text"],
        )

        self.assertNotIn(
            "display: none",
            result["text"],
        )

        self.assertNotIn(
            "Subscribe to our newsletter",
            result["text"],
        )

    def test_normalizes_whitespace(self):
        html = """
        <html>
          <body>
            <article>
              <h1>
                Team       wins
                dramatic final
              </h1>

              <p>
                The team   scored twice
                during the closing minutes
                of the match.
              </p>

              <p>
                Supporters celebrated
                throughout the stadium
                after the final whistle.
              </p>
            </article>
          </body>
        </html>
        """

        result = main.extract_article_content(
            html
        )

        self.assertEqual(
            result["title"],
            "Team wins dramatic final",
        )

        self.assertIn(
            (
                "The team scored twice during the "
                "closing minutes of the match."
            ),
            result["text"],
        )

        self.assertNotIn(
            "  ",
            result["text"],
        )

    def test_rejects_page_without_meaningful_text(self):
        html = """
        <html>
          <head>
            <title>Empty sports page</title>
          </head>
          <body>
            <article>
              <p>Brief update.</p>
            </article>
          </body>
        </html>
        """

        with self.assertRaises(ValueError):
            main.extract_article_content(
                html
            )

    def test_caps_extracted_text_length(self):
        long_paragraph = (
            "This sentence contains relevant "
            "sports reporting details. "
        ) * 20

        html = f"""
        <html>
          <body>
            <article>
              <h1>Long sports report</h1>
              <p>{long_paragraph}</p>
            </article>
          </body>
        </html>
        """

        result = main.extract_article_content(
            html,
            max_chars=160,
            min_chars=40,
        )

        self.assertLessEqual(
            len(result["text"]),
            160,
        )

        self.assertGreaterEqual(
            len(result["text"]),
            40,
        )


    def test_chooses_meaningful_article_when_first_is_empty(
        self,
    ):
        html = """
        <html>
          <body>
            <article>
            </article>

            <article>
              <h1>
                Transfer race intensifies
              </h1>

              <p>
                Barcelona are preparing a new move
                for the midfielder after further
                discussions with club officials.
              </p>

              <p>
                The negotiations are expected to
                continue during the coming week as
                both sides assess the situation.
              </p>
            </article>
          </body>
        </html>
        """

        result = main.extract_article_content(
            html
        )

        self.assertEqual(
            result["title"],
            "Transfer race intensifies",
        )

        self.assertIn(
            "Barcelona are preparing",
            result["text"],
        )

        self.assertIn(
            "negotiations are expected",
            result["text"],
        )

        self.assertEqual(
            result["extraction_method"],
            "article",
        )

        self.assertEqual(
            result["paragraph_count"],
            2,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
