# tawzia-chat

Interface de conversation IA pour Tawzia (assistant-ui + CCv2)

## Installation instructions

```sh
uv pip install tawzia-chat
```

### Development install (editable)

When developing this component locally, install it in editable mode so Streamlit picks up code changes without rebuilding a wheel. Run this from the directory that contains `pyproject.toml`:

```sh
uv pip install -e . --force-reinstall
```

## Usage instructions

Python détient la conversation, le composant l'affiche, et chaque envoi remonte
par un déclencheur. La réponse est produite côté serveur : **aucune clé d'API ne
descend dans le navigateur**.

```python
import streamlit as st

from tawzia_chat import tawzia_chat

st.session_state.setdefault("messages", [])

result = tawzia_chat(
    st.session_state["messages"],          # [{"role": "user"|"assistant", "content": str}]
    busy=False,                            # True pendant le calcul de la réponse
    placeholder="Posez une question…",
    suggestions=["Une première question ?"],
    empty_title="Que voulez-vous savoir ?",
    empty_text="Affiché tant que le fil est vide.",
    key="thread",
)

if result.sent:                            # le message envoyé lors de ce rerun
    st.session_state["messages"].append({"role": "user", "content": result.sent})
    st.rerun()
```

Voir `example.py` pour la boucle complète en deux temps (afficher la question,
puis produire la réponse), qui est celle utilisée par l'application.

## Build a wheel

To package this component for distribution:

1. Build the frontend assets (from `tawzia_chat/frontend`):

   ```sh
   npm i
   npm run build
   ```

2. Build the Python wheel using UV (from the project root):
   ```sh
   uv build
   ```

This will create a `dist/` directory containing your wheel. The wheel includes the compiled frontend from `tawzia_chat/frontend/build`.

### Requirements

- Python >= 3.10
- Node.js >= 24 (LTS)

### Expected output

- `dist/tawzia_chat-0.0.1-py3-none-any.whl`
- If you run `uv run --with build python -m build` (without `--wheel`), you’ll also get an sdist: `dist/tawzia-chat-0.0.1.tar.gz`
