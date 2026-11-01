# Vendored scripts

- `Sortable.min.js` — [SortableJS](https://github.com/SortableJS/Sortable)
  **1.15.6**, MIT (`Sortable.LICENSE`), pinned for the forum structure tree
  (todo 668). Wagtail bundles its own copy inside `wagtailadmin/js/vendor.js`,
  which is not a public API, so the package ships this one.
  Taken unmodified from the npm tarball `sortablejs-1.15.6.tgz`
  (`sha512-aNfiuwMEpfBM/CN6LY0ibyhxPfPbyFeBTYJKCvzkJ2GkUpazIt3H+QIPAMHwqQ7tMKaHz1Qj+rJJCqljnf4p3A==`);
  upstream file sha256
  `6d0a831fc19b4bae851797ad3393157e861afb7862459c11226359b27e2c4337`.
  The repo's end-of-file fixer added one trailing newline, so the file here
  is that plus `\n`. To upgrade, replace the file, the version above and both
  hashes.
