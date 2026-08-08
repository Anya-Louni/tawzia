import {
  FrontendRenderer,
  FrontendRendererArgs,
} from "@streamlit/component-v2-lib";
import { StrictMode } from "react";
import { createRoot, Root } from "react-dom/client";

import Chat, { ChatDataShape, ChatStateShape } from "./Chat";

// Handle the possibility of multiple instances of the component to keep track
// of the React roots for each component instance.
const reactRoots: WeakMap<FrontendRendererArgs["parentElement"], Root> =
  new WeakMap();

const ChatRoot: FrontendRenderer<ChatStateShape, ChatDataShape> = (args) => {
  const { data, parentElement, setTriggerValue } = args;

  const rootElement = parentElement.querySelector(".react-root");

  if (!rootElement) {
    throw new Error("Unexpected: React root element not found");
  }

  let reactRoot = reactRoots.get(parentElement);
  if (!reactRoot) {
    reactRoot = createRoot(rootElement);
    reactRoots.set(parentElement, reactRoot);
  }

  // Toutes les données viennent de Python : ce fichier est le pont, il doit
  // donc extraire chaque champ explicitement, sinon les props arrivent
  // `undefined` côté React.
  const {
    messages,
    busy,
    placeholder,
    suggestions,
    emptyTitle,
    emptyText,
  } = data;

  reactRoot.render(
    <StrictMode>
      <Chat
        messages={messages ?? []}
        busy={busy ?? false}
        placeholder={placeholder ?? ""}
        suggestions={suggestions ?? []}
        emptyTitle={emptyTitle ?? ""}
        emptyText={emptyText ?? ""}
        setTriggerValue={setTriggerValue}
      />
    </StrictMode>,
  );

  return () => {
    const root = reactRoots.get(parentElement);

    if (root) {
      root.unmount();
      reactRoots.delete(parentElement);
    }
  };
};

export default ChatRoot;
