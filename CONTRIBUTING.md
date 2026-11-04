# Contributing

Start with an issue describing the problem, the intended behavior and a small reproducible example. Use synthetic inputs where possible. Keep customer models, license data, personal paths and approval identities out of public issues and commits.

Run the offline suite from the repository root:

```console
python -m unittest discover -s tests -v
```

Changes to the executor should preserve these guarantees:

- Planning does not start COMSOL; real execution requires two distinct human decisions for the current plan.
- Input, code or configuration changes invalidate earlier approval records.
- Exports refer to the solution produced by the reviewed solver sequence.
- Compilation, execution, numerical comparison and engineering validation remain separate evidence claims.
- Failures and interrupted runs retain useful records and cannot become a false success.

For a new COMSOL feature, cite the matching version's official API or a reviewed configuration export. Add a narrow regression test for the behavior changed. Record separately whether a real COMSOL model was loaded or solved; a mocked process is not an integration test.

Domain builders and additional COMSOL versions are welcome as separate adapters with a bounded example and explicit assumptions. The current runnable adapter remains scoped to COMSOL 6.3 on Windows.

Contributions are submitted under the repository's [MIT license](LICENSE). Documentation in either Chinese or English is welcome.
