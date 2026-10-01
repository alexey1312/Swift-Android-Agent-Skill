# Skip's official skills

The Skip team publishes agent skills for Skip projects at
<https://github.com/skiptools/skills> (Apache-2.0),
linked from skip.dev's FAQ.
They own Skip's ground — creating a project, `skip.yml`, SwiftUI on Android,
icons, localization, test runners and store release.
Route those items to them by name;
this repository's skills cover the decision, the shared core, the boundary,
and the Swift SDK underneath.

Checked at commit
[`0399f0a`](https://github.com/skiptools/skills/tree/0399f0a2046635e268b37f43f5c370b32b7557db/)
(2026-09-29, still the head of `main` on 2026-10-01).

## Install

```bash
/plugin marketplace add skiptools/skills
/plugin install skip-app-design@skiptools-skills
/plugin install skip-testing-deployment@skiptools-skills
```

Installs failed with a manifest validation error until the fix merged on 2026-09-29
(skiptools/skills issue #3, pull request #5);
refresh the marketplace if it was added earlier.

## The eleven skills

| Plugin | Skill | Route items about |
| --- | --- | --- |
| `skip-app-design` | `skip-app-walkthrough` | the order of work in a new Skip app |
| `skip-app-design` | `skip-project-creation` | `skip init` and `skip create`, flags, framework dependencies |
| `skip-app-design` | `building-skip-ui` | SwiftUI views in Skip projects, `ComposeView`, Material 3 |
| `skip-app-design` | `skip-fuse` | native mode: `skip.yml` (`mode`, `bridging`, `kotlincompat`), `import SkipFuse`, `AnyDynamicObject`, `skip android test` |
| `skip-app-design` | `skip-lite-transpilation` | transpiled-mode pitfalls and `// SKIP` directives |
| `skip-app-design` | `skip-frameworks` | Skip's framework modules (SQL, Keychain, Web, Firebase, media…) |
| `skip-app-design` | `skip-icons` | icons instead of `Image(systemName:)` |
| `skip-app-design` | `skip-localization` | string catalogs and store metadata |
| `skip-testing-deployment` | `skip-testing` | XCTest, Swift Testing, parity tests, Robolectric |
| `skip-testing-deployment` | `skip-ui-automation` | `skip app launch` and Maestro flows |
| `skip-testing-deployment` | `skip-deployment` | `skip export`, signing, fastlane, store upload |

## Where they disagree with skip.dev (as of 2026-10-01, commit `0399f0a`)

Each item names the line, what skip.dev says instead, and how to re-check it.
When they conflict, follow skip.dev.

1. **Lite as the default mode.**
   `skip-fuse` line 21 says to default to Lite unless a listed reason applies;
   `skip-app-walkthrough` line 29 says to default to Lite;
   `skip-project-creation` line 58 calls Lite best for most projects.
   skip.dev recommends native (Fuse) mode for most apps (skip.dev › Modes; skip.dev › Project Types).
   Permalinks:
   [skip-fuse L21](https://github.com/skiptools/skills/blob/0399f0a2046635e268b37f43f5c370b32b7557db/plugins/skip-app-design/skills/skip-fuse/SKILL.md#L21),
   [skip-app-walkthrough L29](https://github.com/skiptools/skills/blob/0399f0a2046635e268b37f43f5c370b32b7557db/plugins/skip-app-design/skills/skip-app-walkthrough/SKILL.md#L29),
   [skip-project-creation L58](https://github.com/skiptools/skills/blob/0399f0a2046635e268b37f43f5c370b32b7557db/plugins/skip-app-design/skills/skip-project-creation/SKILL.md#L58).
2. **Debugging native Swift.**
   `skip-fuse` (description, lines 264–266) says breakpoint debugging of native Swift on Android
   is not supported and LLDB is not generally available.
   LLDB has debugged Swift on Android from the command line and VS Code since Swift 6.3;
   what is still missing is Swift breakpoints in Android Studio
   (`versions.md` › Debugging; Swift Forums › Swift debugging on Android: current state).
   [skip-fuse L264](https://github.com/skiptools/skills/blob/0399f0a2046635e268b37f43f5c370b32b7557db/plugins/skip-app-design/skills/skip-fuse/SKILL.md#L264).
3. **A reference build that does not exist.**
   The README and `skip-app-walkthrough` point at a `skipapp-todo` sample,
   in two different places; neither exists publicly
   (`gh api repos/skiptools/skipapp-todo` returns 404).
   [skip-app-walkthrough L142](https://github.com/skiptools/skills/blob/0399f0a2046635e268b37f43f5c370b32b7557db/plugins/skip-app-design/skills/skip-app-walkthrough/SKILL.md#L142).
4. **An `AGENTS.md` that does not exist.**
   README line 56 tells other agents to read `AGENTS.md`; the repository has none.
   [README L56](https://github.com/skiptools/skills/blob/0399f0a2046635e268b37f43f5c370b32b7557db/README.md#L56).
5. **A test-library value the CLI does not accept.**
   `skip-testing` line 89 passes `--testing-library swift-testing`;
   Skip's CLI reference and its source accept `all`, `xctest` or `testing`
   (skip.dev › Skip CLI Reference).
   [skip-testing L89](https://github.com/skiptools/skills/blob/0399f0a2046635e268b37f43f5c370b32b7557db/plugins/skip-testing-deployment/skills/skip-testing/SKILL.md#L89).
6. **A dated CI recipe.**
   `skip-deployment/references/cicd.md` uses `macos-14` runners, JDK 17,
   the old `brew install skiptools/skip/skip` tap,
   and runs plain `swift test` on an emulator, with no native-mode (`skip android test`) job.
   `ci.md` lists current recipes.
   [cicd.md L17–L36](https://github.com/skiptools/skills/blob/0399f0a2046635e268b37f43f5c370b32b7557db/plugins/skip-testing-deployment/skills/skip-deployment/references/cicd.md#L17-L36).
7. **Nothing on Combine or streams at the boundary.**
   No file covers Combine, `ObservableObject` or `AsyncStream` in native mode,
   which is where Polymarket's report says the bridge stops (`bridge-surface.md`).

Not a disagreement, but worth knowing:
`skip-fuse` line 56 says a Fuse app typically uses a single module;
a shared core under native UI is several modules by design
(the Polymarket report in `sources.md`).

## Re-checking

```bash
gh api repos/skiptools/skills/commits/main --jq '.sha + " " + .commit.committer.date'
gh api repos/skiptools/skills/contents/plugins/skip-app-design/skills/skip-fuse/SKILL.md \
  --jq .content | base64 -d | grep -n -i -E 'default to|breakpoint|lldb'
gh api repos/skiptools/skipapp-todo --silent && echo exists || echo missing
```

When the head moves, re-read the items above and update the commit and the date here.
