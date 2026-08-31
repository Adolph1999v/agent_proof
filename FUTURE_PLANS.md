# AgentProof Future Plans

These are planned improvements. They are not claims about the current version.

## More programming languages

- **What:** Add checks for JavaScript, TypeScript, Java, Go, Rust, and more test tools.
- **Why:** AgentProof currently creates independent challenges only for Python and pytest.
- **Benefit:** More developers can verify their projects with the same workflow.

## Stronger isolation

- **What:** Run project code inside a locked container or virtual machine.
- **Why:** A disposable copy protects the source folder, but test code still runs on the local system.
- **Benefit:** Users can inspect less-trusted projects with lower risk.

## Large-project understanding

- **What:** Build a local code index and send only the most useful files to the model.
- **Why:** A large project cannot fit safely into one model request.
- **Benefit:** Challenges stay faster, cheaper in memory, and more focused.

## Automatic checks after changes

- **What:** Watch approved projects and run AgentProof after an agent finishes a change.
- **Why:** Manually starting every review is easy to forget.
- **Benefit:** Problems are found earlier with less work from the user.

## Git, pull-request, and coding-agent links

- **What:** Connect AgentProof to Git checks, pull requests, Codex, Claude Code, and OpenCode.
- **Why:** Verification should fit the tools developers already use.
- **Benefit:** Teams can review proof beside the change instead of copying details by hand.

## Baseline history and recovery

- **What:** Let users view older approved baselines, restore one, and export or reapply a safe change.
- **Why:** The current version keeps baseline history but does not provide full recovery tools.
- **Benefit:** Users can return to a known working state more easily.

## Hardware-aware model choice

- **What:** Compare local models for correctness, speed, token use, and memory use, then recommend one
  for the user's computer.
- **Why:** A larger model is not always the fastest or most reliable choice.
- **Benefit:** Users get dependable checks without overloading their system.

## A larger real-world evaluation

- **What:** Test AgentProof on more public bugs, safe patches, languages, and project sizes.
- **Why:** Eleven cases show the current result but cannot represent every project.
- **Benefit:** Users and reviewers get stronger evidence about where AgentProof works well.

## Easier evidence sharing

- **What:** Create clear HTML reports, private-data removal tools, and signed result files.
- **Why:** Raw JSON evidence is useful but not easy for every reviewer to read or share.
- **Benefit:** Teams can understand and trust a result without exposing private code.

## Optional desktop launcher

- **What:** Package the local web app with a simple launcher for macOS, Windows, and Linux.
- **Why:** The browser interface is portable, but setup still uses a terminal.
- **Benefit:** Non-technical users can start AgentProof and choose a project more easily.
