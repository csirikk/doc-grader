# Overleaf-Git link (thesis/)

## Daily use

Pull Overleaf changes

```bash
git fetch overleaf
git subtree pull --prefix=thesis overleaf master
```

Push local committed changes in `thesis/` back to Overleaf

```bash
git subtree push --prefix=thesis overleaf master
```

Then push the repo branch to GitHub

```bash
git push origin design
```
