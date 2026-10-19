from pathlib import Path
import re
import unittest


class WorkflowTests(unittest.TestCase):
    def test_publication_boundary_and_action_pins(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    '.github/workflows/pages.yml').read_text()
        # Static checks deliberately target this workflow's indentation/layout;
        # changes to its structure require review, without a YAML dependency.
        gate = ("github.ref == 'refs/heads/main' && "
                "github.event_name != 'pull_request' && "
                "vars.PAGES_PUBLICATION_APPROVED == 'true'")
        deploy = workflow.split('\n  deploy:\n', 1)[1]
        self.assertIn('\n    if: ' + gate + '\n', '\n' + deploy)

        steps = re.findall(r'^      - .*?(?=^\S|^  \S|^      - |\Z)',
                           workflow, re.MULTILINE | re.DOTALL)
        uploads = [step for step in steps if 'uses: actions/upload-' in step]
        self.assertEqual(len(uploads), 1)
        self.assertIn('uses: actions/upload-pages-artifact@', uploads[0])
        self.assertIn('\n        if: ' + gate + '\n', uploads[0])
        self.assertEqual(re.findall(r'^\s+path: (.+)$', workflow, re.MULTILINE),
                         ['site/'])
        self.assertRegex(uploads[0], r'\n        with:\n          path: site/\n\Z')

        uses = re.findall(r'^\s+(?:- )?uses:\s*(.+)$', workflow, re.MULTILINE)
        self.assertTrue(uses)
        for action in uses:
            with self.subTest(action=action):
                self.assertRegex(action, r'^[\w./-]+@[0-9a-f]{40}(?:\s+#.*)?$')


if __name__ == '__main__':
    unittest.main()
