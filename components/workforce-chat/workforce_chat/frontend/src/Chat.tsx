import {
  AssistantRuntimeProvider,
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useExternalStoreRuntime,
  type AppendMessage,
  type ThreadMessageLike,
} from "@assistant-ui/react";
import { FC, ReactElement, useCallback } from "react";

import { FrontendRendererArgs } from "@streamlit/component-v2-lib";

/** Un message tel que Python l'envoie. */
export type WfMessage = {
  role: "user" | "assistant" | "system";
  content: string;
};

/** Les clés que le composant renvoie à Python. `sent` est un déclencheur. */
export type ChatStateShape = {
  sent: string;
};

export type ChatDataShape = {
  messages: WfMessage[];
  busy: boolean;
  placeholder: string;
  suggestions: string[];
  emptyTitle: string;
  emptyText: string;
};

export type ChatProps = Pick<
  FrontendRendererArgs<ChatStateShape, ChatDataShape>,
  "setTriggerValue"
> &
  ChatDataShape;

/**
 * Les styles vivent dans une balise <style> à l'intérieur du composant plutôt
 * que dans un fichier CSS séparé : CCv2 monte le composant dans un shadow root,
 * donc la portée est déjà garantie, et on évite d'avoir à faire correspondre un
 * glob `index-*.css` au fichier produit par le bundler.
 *
 * Les couleurs proviennent des variables `--st-*` injectées par Streamlit : le
 * composant suit donc automatiquement le thème de l'application.
 */
const STYLES = `
.wf-thread {
  display: flex; flex-direction: column; height: 560px;
  border: 1px solid var(--st-border-color, #CBD5E1);
  border-radius: 8px; background: var(--st-secondary-background-color, #fff);
  overflow: hidden;
  font-family: var(--st-font, 'Inter', system-ui, sans-serif);
}
.wf-viewport {
  flex: 1 1 auto; overflow-y: auto; padding: 20px;
  display: flex; flex-direction: column; gap: 14px;
}
.wf-empty { margin: auto; text-align: center; max-width: 460px; padding: 20px; }
.wf-empty h3 {
  margin: 0 0 8px; font-size: 17px; font-weight: 800;
  color: var(--st-text-color, #0F172A); letter-spacing: -.015em;
}
.wf-empty p {
  margin: 0 0 18px; font-size: 13.5px; line-height: 1.55;
  color: var(--st-gray-color, #475569);
}
.wf-suggestions { display: flex; flex-direction: column; gap: 8px; }
.wf-suggestion {
  text-align: left; padding: 11px 14px; font-size: 13.5px; font-weight: 500;
  border: 1px solid var(--st-border-color, #CBD5E1); border-radius: 7px;
  background: var(--st-background-color, #fff);
  color: var(--st-text-color, #0F172A); cursor: pointer;
  transition: border-color .13s ease, background .13s ease, transform .13s ease;
}
.wf-suggestion:hover {
  border-color: var(--st-primary-color, #1355C4);
  background: rgba(19, 85, 196, .06);
  transform: translateY(-1px);
}
.wf-row { display: flex; }
.wf-row.user { justify-content: flex-end; }
.wf-bubble {
  max-width: 76%; padding: 11px 15px; border-radius: 10px;
  font-size: 14px; line-height: 1.6; white-space: pre-wrap; word-break: break-word;
}
.wf-row.user .wf-bubble {
  background: var(--st-primary-color, #1355C4); color: #fff;
  border-bottom-right-radius: 3px;
}
.wf-row.assistant .wf-bubble {
  background: var(--st-background-color, #F1F5F9);
  color: var(--st-text-color, #0F172A);
  border: 1px solid var(--st-border-color, #CBD5E1);
  border-bottom-left-radius: 3px;
}
.wf-role {
  font-size: 11px; font-weight: 700; letter-spacing: .04em;
  text-transform: uppercase; opacity: .65; margin-bottom: 4px;
}
.wf-typing { display: inline-flex; gap: 4px; align-items: center; height: 18px; }
.wf-typing span {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--st-gray-color, #475569); opacity: .45;
  animation: wf-blink 1.25s infinite ease-in-out;
}
.wf-typing span:nth-child(2) { animation-delay: .18s; }
.wf-typing span:nth-child(3) { animation-delay: .36s; }
@keyframes wf-blink {
  0%, 80%, 100% { opacity: .25; transform: translateY(0); }
  40% { opacity: .9; transform: translateY(-3px); }
}
.wf-composer {
  display: flex; gap: 10px; padding: 12px;
  border-top: 1px solid var(--st-border-color, #CBD5E1);
  background: var(--st-secondary-background-color, #fff);
}
.wf-input {
  flex: 1 1 auto; resize: none; min-height: 42px; max-height: 140px;
  padding: 11px 13px; font-size: 14px; font-family: inherit;
  border: 1px solid var(--st-border-color, #CBD5E1); border-radius: 7px;
  background: var(--st-background-color, #fff);
  color: var(--st-text-color, #0F172A); outline: none;
  transition: border-color .13s ease, box-shadow .13s ease;
}
.wf-input:focus {
  border-color: var(--st-primary-color, #1355C4);
  box-shadow: 0 0 0 3px rgba(19, 85, 196, .16);
}
.wf-send {
  min-height: 42px; padding: 0 20px; font-size: 14px; font-weight: 600;
  border-radius: 7px; cursor: pointer; border: 1px solid var(--st-primary-color, #1355C4);
  background: var(--st-primary-color, #1355C4); color: #fff;
  transition: filter .13s ease, transform .13s ease;
}
.wf-send:hover { filter: brightness(.92); transform: translateY(-1px); }
.wf-send:disabled { opacity: .45; cursor: not-allowed; transform: none; }
`;

const convertMessage = (message: WfMessage): ThreadMessageLike => ({
  role: message.role,
  content: [{ type: "text", text: message.content }],
});

const UserMessage: FC = () => (
  <MessagePrimitive.Root className="wf-row user">
    <div className="wf-bubble">
      <MessagePrimitive.Parts />
    </div>
  </MessagePrimitive.Root>
);

const AssistantMessage: FC = () => (
  <MessagePrimitive.Root className="wf-row assistant">
    <div className="wf-bubble">
      <div className="wf-role">WorkForce.dz</div>
      <MessagePrimitive.Parts />
    </div>
  </MessagePrimitive.Root>
);

/**
 * L'interface de conversation, bâtie sur assistant-ui.
 *
 * Le fil est piloté par un *external store* : Python détient la vérité (la
 * liste des messages), le composant l'affiche, et chaque envoi remonte à Python
 * par un déclencheur CCv2. C'est le bon découpage ici, parce que la réponse est
 * produite côté serveur par Groq et par les moteurs maison , le navigateur ne
 * doit jamais détenir de clé d'API.
 */
const Chat: FC<ChatProps> = ({
  messages,
  busy,
  placeholder,
  suggestions,
  emptyTitle,
  emptyText,
  setTriggerValue,
}): ReactElement => {
  const send = useCallback(
    (text: string) => {
      const clean = text.trim();
      if (clean) setTriggerValue("sent", clean);
    },
    [setTriggerValue],
  );

  const onNew = useCallback(
    async (message: AppendMessage) => {
      const text = message.content
        .filter((part): part is { type: "text"; text: string } =>
          part.type === "text",
        )
        .map((part) => part.text)
        .join("\n");
      send(text);
    },
    [send],
  );

  const runtime = useExternalStoreRuntime<WfMessage>({
    messages,
    isRunning: busy,
    convertMessage,
    onNew,
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <style>{STYLES}</style>
      <ThreadPrimitive.Root className="wf-thread">
        <ThreadPrimitive.Viewport className="wf-viewport" autoScroll>
          <ThreadPrimitive.Empty>
            <div className="wf-empty">
              <h3>{emptyTitle}</h3>
              <p>{emptyText}</p>
              <div className="wf-suggestions">
                {suggestions.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    className="wf-suggestion"
                    onClick={() => send(suggestion)}
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          </ThreadPrimitive.Empty>

          <ThreadPrimitive.Messages
            components={{
              UserMessage,
              AssistantMessage,
            }}
          />

          {busy && (
            <div className="wf-row assistant">
              <div className="wf-bubble">
                <span className="wf-typing">
                  <span />
                  <span />
                  <span />
                </span>
              </div>
            </div>
          )}
        </ThreadPrimitive.Viewport>

        <ComposerPrimitive.Root className="wf-composer">
          <ComposerPrimitive.Input
            className="wf-input"
            placeholder={placeholder}
            rows={1}
            autoFocus
          />
          <ComposerPrimitive.Send className="wf-send" disabled={busy}>
            Envoyer
          </ComposerPrimitive.Send>
        </ComposerPrimitive.Root>
      </ThreadPrimitive.Root>
    </AssistantRuntimeProvider>
  );
};

export default Chat;
