# Repository instructions

For simulation work, read `skills/comsol-multiphysics/SKILL.md` and follow its evidence, assumption-review, solve-approval, and validation workflow. This is the authoritative agent entrypoint.

The reusable Skill and COMSOL 6.3 executor have different responsibilities. Keep engineering decisions in traceable case inputs, and version-specific API behavior in the executor. Verify API features against COMSOL 6.3 documentation or exported Java.

Keep customer models, machine paths, credentials, licenses, results, and approval identities outside the public repository. Treat fixture tests, Java compilation, real solves, numerical reproduction, and engineering validation as distinct evidence levels.
