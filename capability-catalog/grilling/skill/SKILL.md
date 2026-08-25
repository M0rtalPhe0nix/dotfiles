---
name: grilling
description: Grill the user relentlessly about a plan, decision, or idea. Use when the user wants to stress-test their thinking or uses any grill trigger phrase.
---

# Grilling

Interview the user relentlessly until reaching a shared understanding. Map the subject as a **design tree**: every decision branches into the decisions that depend on it.

Work the tree in **rounds**. The **frontier** is every decision whose prerequisites are already settled: the questions that can be asked now without guessing at answers not yet heard. Ask the whole frontier in one round, number each question, and give a recommended answer. Then wait for the user's answers before the next round.

Format a round like this:

```text
❓ **Q1** - **<question title>**: <question body, which may include multiple paragraphs or choices>

➡️ <recommended answer>

---

❓ **Q2** - **<question title>**: <question body, which may include multiple paragraphs or choices>

➡️ <recommended answer>
```

Each round reshapes the tree: settled decisions push the frontier outward and unblock questions that depend on them. Recompute the frontier and ask the next round. Put a question whose answer depends on another question still open in the current round in a later round.

Finding **facts** is the agent's job, never the user's. When a frontier question needs a fact from the environment, such as the filesystem or another tool, dispatch a sub-agent to find it instead of asking the user. Do not block the entire round on it: treat the running exploration as an unsettled prerequisite, defer only its downstream questions, and ask the rest of the frontier now. The **decisions** are the user's: put each one to the user and wait.

Finish only when the frontier is empty: every branch of the design tree has been visited and nothing remains silently assumed. Do not act on the result until the user confirms that shared understanding has been reached.
