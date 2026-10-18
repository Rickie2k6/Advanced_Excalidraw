//đây là command line chạy trong server: corepack yarn start --host 10.255.0.11
/* gọi lệnh này để activate cái Cloudfkare Tunnel: ~/bin/cloudflared tunnel \
  --url http://10.255.0.11:65533*/
  import PromptPage from "./PromptPage";
  import {
  Excalidraw,
  LiveCollaborationTrigger,
  TTDDialogTrigger,
  CaptureUpdateAction,
  reconcileElements,
  useEditorInterface,
  ExcalidrawAPIProvider,
  useExcalidrawAPI,
  exportToBlob,
  convertToExcalidrawElements,
} from "@excalidraw/excalidraw";
import { trackEvent } from "@excalidraw/excalidraw/analytics";
import { getDefaultAppState } from "@excalidraw/excalidraw/appState";
import {
  expressionToFreedraw,
  measureMathExpression,
} from "./math-freedraw";
import { animateMathHandwriting } from "./math-handwriting-animation";
import {
  findAvailablePosition,
  estimateMathSize,
} from "./math-placement";
import {
  CommandPalette,
  DEFAULT_CATEGORIES,
} from "@excalidraw/excalidraw/components/CommandPalette/CommandPalette";
import { ErrorDialog } from "@excalidraw/excalidraw/components/ErrorDialog";
import { OverwriteConfirmDialog } from "@excalidraw/excalidraw/components/OverwriteConfirm/OverwriteConfirm";
import { openConfirmModal } from "@excalidraw/excalidraw/components/OverwriteConfirm/OverwriteConfirmState";
import { ShareableLinkDialog } from "@excalidraw/excalidraw/components/ShareableLinkDialog";
import Trans from "@excalidraw/excalidraw/components/Trans";
import {
  APP_NAME,
  EVENT,
  VERSION_TIMEOUT,
  debounce,
  getVersion,
  getFrame,
  isTestEnv,
  preventUnload,
  resolvablePromise,
  isRunningInIframe,
  isDevEnv,
} from "@excalidraw/common";
import polyfill from "@excalidraw/excalidraw/polyfill";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { loadFromBlob } from "@excalidraw/excalidraw/data/blob";
import { t } from "@excalidraw/excalidraw/i18n";

import {
  isFreeDrawElement,
} from "@excalidraw/element";

import {
  GithubIcon,
  XBrandIcon,
  DiscordIcon,
  ExcalLogo,
  usersIcon,
  exportToPlus,
  share,
  youtubeIcon,
} from "@excalidraw/excalidraw/components/icons";
import { isElementLink } from "@excalidraw/element";
import {
  bumpElementVersions,
  restoreAppState,
  restoreElements,
} from "@excalidraw/excalidraw/data/restore";
import { newElementWith } from "@excalidraw/element";
import { isInitializedImageElement } from "@excalidraw/element";
import clsx from "clsx";
import {
  parseLibraryTokensFromUrl,
  useHandleLibrary,
} from "@excalidraw/excalidraw/data/library";

import type { RemoteExcalidrawElement } from "@excalidraw/excalidraw/data/reconcile";
import type { RestoredDataState } from "@excalidraw/excalidraw/data/restore";
import type {
  FileId,
  NonDeletedExcalidrawElement,
  OrderedExcalidrawElement,
} from "@excalidraw/element/types";
import type {
  AppState,
  ExcalidrawImperativeAPI,
  BinaryFiles,
  ExcalidrawInitialDataState,
  UIAppState,
  ExcalidrawProps,
} from "@excalidraw/excalidraw/types";
import type { ResolutionType } from "@excalidraw/common/utility-types";
import type { ResolvablePromise } from "@excalidraw/common/utils";

import CustomStats from "./CustomStats";
import {
  Provider,
  useAtom,
  useAtomValue,
  useAtomWithInitialValue,
  appJotaiStore,
} from "./app-jotai";
import {
  FIREBASE_STORAGE_PREFIXES,
  isExcalidrawPlusSignedUser,
  STORAGE_KEYS,
  SYNC_BROWSER_TABS_TIMEOUT,
} from "./app_constants";
import Collab, {
  collabAPIAtom,
  isCollaboratingAtom,
  isOfflineAtom,
  userToFollowAtom,
} from "./collab/Collab";
import { AppFooter } from "./components/AppFooter";
import { AppMainMenu } from "./components/AppMainMenu";
import { AppWelcomeScreen } from "./components/AppWelcomeScreen";
import {
  ExportToExcalidrawPlus,
  exportToExcalidrawPlus,
} from "./components/ExportToExcalidrawPlus";
import { TopErrorBoundary } from "./components/TopErrorBoundary";

import {
  exportToBackend,
  getCollaborationLinkData,
  importFromBackend,
  isCollaborationLink,
} from "./data";

import { updateStaleImageStatuses } from "./data/FileManager";
import { FileStatusStore } from "./data/fileStatusStore";
import {
  importFromLocalStorage,
  importUsernameFromLocalStorage,
} from "./data/localStorage";

import { loadFilesFromFirebase } from "./data/firebase";
import {
  LibraryIndexedDBAdapter,
  LibraryLocalStorageMigrationAdapter,
  LocalData,
  localStorageQuotaExceededAtom,
} from "./data/LocalData";
import { isBrowserStorageStateNewer } from "./data/tabSync";
import { ShareDialog, shareDialogStateAtom } from "./share/ShareDialog";
import CollabError, { collabErrorIndicatorAtom } from "./collab/CollabError";
import { useHandleAppTheme } from "./useHandleAppTheme";
import { getPreferredLanguage } from "./app-language/language-detector";
import { useAppLangCode } from "./app-language/language-state";
import DebugCanvas, {
  debugRenderer,
  isVisualDebuggerEnabled,
  loadSavedDebugState,
} from "./components/DebugCanvas";
import { useSimulatedCollaborators } from "./debugCollaborators";
import { AIComponents } from "./components/AI";
import { ExcalidrawPlusIframeExport } from "./ExcalidrawPlusIframeExport";

import "./index.scss";

import { ExcalidrawPlusPromoBanner } from "./components/ExcalidrawPlusPromoBanner";
import { AppSidebar } from "./components/AppSidebar";

import type { CollabAPI } from "./collab/Collab";

polyfill();

window.EXCALIDRAW_THROTTLE_RENDER = true;

declare global {
  interface BeforeInstallPromptEventChoiceResult {
    outcome: "accepted" | "dismissed";
  }

  interface BeforeInstallPromptEvent extends Event {
    prompt(): Promise<void>;
    userChoice: Promise<BeforeInstallPromptEventChoiceResult>;
  }

  interface WindowEventMap {
    beforeinstallprompt: BeforeInstallPromptEvent;
  }
}

let pwaEvent: BeforeInstallPromptEvent | null = null;

// Adding a listener outside of the component as it may (?) need to be
// subscribed early to catch the event.
//
// Also note that it will fire only if certain heuristics are met (user has
// used the app for some time, etc.)
window.addEventListener(
  "beforeinstallprompt",
  (event: BeforeInstallPromptEvent) => {
    // prevent Chrome <= 67 from automatically showing the prompt
    event.preventDefault();
    // cache for later use
    pwaEvent = event;
  },
);

let isSelfEmbedding = false;

if (window.self !== window.top) {
  try {
    const parentUrl = new URL(document.referrer);
    const currentUrl = new URL(window.location.href);
    if (parentUrl.origin === currentUrl.origin) {
      isSelfEmbedding = true;
    }
  } catch (error) {
    // ignore
  }
}

const shareableLinkConfirmDialog = {
  title: t("overwriteConfirm.modal.shareableLink.title"),
  description: (
    <Trans
      i18nKey="overwriteConfirm.modal.shareableLink.description"
      bold={(text) => <strong>{text}</strong>}
      br={() => <br />}
    />
  ),
  actionLabel: t("overwriteConfirm.modal.shareableLink.button"),
  color: "danger",
} as const;

const initializeScene = async (opts: {
  collabAPI: CollabAPI | null;
  excalidrawAPI: ExcalidrawImperativeAPI;
}): Promise<
  { scene: ExcalidrawInitialDataState | null } & (
    | { isExternalScene: true; id: string; key: string }
    | { isExternalScene: false; id?: null; key?: null }
  )
> => {
  const searchParams = new URLSearchParams(window.location.search);
  const id = searchParams.get("id");
  const jsonBackendMatch = window.location.hash.match(
    /^#json=([a-zA-Z0-9_-]+),([a-zA-Z0-9_-]+)$/,
  );
  const externalUrlMatch = window.location.hash.match(/^#url=(.*)$/);

  const localDataState = importFromLocalStorage();

  let scene: Omit<
    RestoredDataState,
    // we're not storing files in the scene database/localStorage, and instead
    // fetch them async from a different store
    "files"
  > & {
    scrollToContent?: boolean;
  } = {
    elements: restoreElements(localDataState?.elements, null, {
      repairBindings: true,
      deleteInvisibleElements: true,
    }),
    appState: restoreAppState(localDataState?.appState, null),
  };

  let roomLinkData = getCollaborationLinkData(window.location.href);
  const isExternalScene = !!(id || jsonBackendMatch || roomLinkData);
  if (isExternalScene) {
    if (
      // don't prompt if scene is empty
      !scene.elements.length ||
      // don't prompt for collab scenes because we don't override local storage
      roomLinkData ||
      // otherwise, prompt whether user wants to override current scene
      (await openConfirmModal(shareableLinkConfirmDialog))
    ) {
      if (jsonBackendMatch) {
        const imported = await importFromBackend(
          jsonBackendMatch[1],
          jsonBackendMatch[2],
        );

        scene = {
          elements: bumpElementVersions(
            restoreElements(imported.elements, null, {
              repairBindings: true,
              deleteInvisibleElements: true,
            }),
            localDataState?.elements,
          ),
          appState: restoreAppState(
            imported.appState,
            // local appState when importing from backend to ensure we restore
            // localStorage user settings which we do not persist on server.
            localDataState?.appState,
          ),
        };
      }
      scene.scrollToContent = true;
      if (!roomLinkData) {
        window.history.replaceState({}, APP_NAME, window.location.origin);
      }
    } else {
      // https://github.com/excalidraw/excalidraw/issues/1919
      if (document.hidden) {
        return new Promise((resolve, reject) => {
          window.addEventListener(
            "focus",
            () => initializeScene(opts).then(resolve).catch(reject),
            {
              once: true,
            },
          );
        });
      }

      roomLinkData = null;
      window.history.replaceState({}, APP_NAME, window.location.origin);
    }
  } else if (externalUrlMatch) {
    window.history.replaceState({}, APP_NAME, window.location.origin);

    const url = externalUrlMatch[1];
    try {
      const request = await fetch(window.decodeURIComponent(url));
      const data = await loadFromBlob(await request.blob(), null, null);
      if (
        !scene.elements.length ||
        (await openConfirmModal(shareableLinkConfirmDialog))
      ) {
        return { scene: data, isExternalScene };
      }
    } catch (error: any) {
      return {
        scene: {
          appState: {
            errorMessage: t("alerts.invalidSceneUrl"),
          },
        },
        isExternalScene,
      };
    }
  }

  if (roomLinkData && opts.collabAPI) {
    const { excalidrawAPI } = opts;

    const scene = await opts.collabAPI.startCollaboration(roomLinkData);

    return {
      // when collaborating, the state may have already been updated at this
      // point (we may have received updates from other clients), so reconcile
      // elements and appState with existing state
      scene: {
        ...scene,
        appState: {
          ...restoreAppState(
            {
              ...scene?.appState,
              theme: localDataState?.appState?.theme || scene?.appState?.theme,
            },
            excalidrawAPI.getAppState(),
          ),
          // necessary if we're invoking from a hashchange handler which doesn't
          // go through App.initializeScene() that resets this flag
          isLoading: false,
        },
        elements: reconcileElements(
          scene?.elements || [],
          excalidrawAPI.getSceneElementsIncludingDeleted() as RemoteExcalidrawElement[],
          excalidrawAPI.getAppState(),
        ),
      },
      isExternalScene: true,
      id: roomLinkData.roomId,
      key: roomLinkData.roomKey,
    };
  } else if (scene) {
    return isExternalScene && jsonBackendMatch
      ? {
          scene,
          isExternalScene,
          id: jsonBackendMatch[1],
          key: jsonBackendMatch[2],
        }
      : { scene, isExternalScene: false };
  }
  return { scene: null, isExternalScene: false };
};

const CHATBOT_BACKEND_URL =
  import.meta.env.VITE_APP_CHATBOT_BACKEND_URL || "";

const CHATBOT_WIDGET_SRC =
  import.meta.env.VITE_APP_CHATBOT_WIDGET_SRC;

const GITHUB_URL =
  import.meta.env.VITE_APP_GITHUB_URL;

const X_URL =
  import.meta.env.VITE_APP_X_URL;

const DISCORD_URL =
  import.meta.env.VITE_APP_DISCORD_URL;

const YOUTUBE_URL =
  import.meta.env.VITE_APP_YOUTUBE_URL;


type EquationGroup = {
  equation_id: string;
  equation: string | null;
  stroke_ids: string[];
  bbox: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  contributors: string[];
  confidence: number | null;
};

type EquationGroupResponse = {
  status: string;
  count: number;
  equations: Record<string, EquationGroup>;
};


type WhiteboardHint = {
  anchor_equation_id: string;
  equation: string;

  bbox: {
    x: number;
    y: number;
    width: number;
    height: number;
  } | null;

  next_step: {
    valid: boolean;
    status: string;
    operation: string | null;
    value: string | null;
    goal: string | null;
  };

  instruction: string;
};

type WhiteboardHintsResponse = {
  success: boolean;
  equation_count: number;
  hints: WhiteboardHint[];
};

type WhiteboardElementSnapshot = {
  id: string;
  type: string;

  x: number;
  y: number;

  width: number;
  height: number;

  angle: number;
  version: number;

  isDeleted: boolean;
};

type WhiteboardActionPayload = {
  action:
    | "create"
    | "move"
    | "resize"
    | "update"
    | "delete";

  element_id: string;
  element_type: string;

  data?: Record<string, unknown>;
};

type HintViewport = {
  scrollX: number;
  scrollY: number;
  zoom: number;
  offsetLeft: number;
  offsetTop: number;
};

const getOrCreateContributorId = () => {
  const storageKey =
    "excalidraw_contributor_id";

  let contributorId =
    localStorage.getItem(storageKey);

  if (!contributorId) {
    contributorId =
      crypto.randomUUID();

    localStorage.setItem(
      storageKey,
      contributorId,
    );
  }

  return contributorId;
};
// gọi chatbot-widget.js
const ExcalidrawWrapper = () => {
  const excalidrawAPI = useExcalidrawAPI();

  const contributorIdRef =
    useRef(
      getOrCreateContributorId(),
    );
  // ============================================================
  // WHITEBOARD TUTOR HINTS
  // ============================================================

  const hintOverlayRootRef =
    useRef<HTMLDivElement>(null);

  const [whiteboardHints, setWhiteboardHints] =
    useState<WhiteboardHint[]>([]);

  const [hintViewport, setHintViewport] =
    useState<HintViewport>({
      scrollX: 0,
      scrollY: 0,
      zoom: 1,
      offsetLeft: 0,
      offsetTop: 0,
    });

  const refreshWhiteboardHints =
    useCallback(async () => {
      try {
        const response = await fetch(
          `${CHATBOT_BACKEND_URL}/api/whiteboard/hints`,
        );

        if (!response.ok) {
          throw new Error(
            `Whiteboard hints failed: ${response.status}`,
          );
        }

        const data =
          (await response.json()) as WhiteboardHintsResponse;

        setWhiteboardHints(
          data.hints ?? [],
        );

        console.log(
          "[Whiteboard Hints]",
          data.hints,
        );
      } catch (error) {
        console.error(
          "[Whiteboard Hints] Failed:",
          error,
        );
      }
    }, []);


  // Load existing hints when app opens.
  useEffect(() => {
    void refreshWhiteboardHints();
  }, [refreshWhiteboardHints]);

useEffect(() => {
  const initializePublicIPv4 = async () => {
    try {
      const response = await fetch(
        `${CHATBOT_BACKEND_URL}/api/client-ip`,
      );

      if (!response.ok) {
        throw new Error(
          `Failed to get client IP: ${response.status}`,
        );
      }

      const data = await response.json();

      if (data.public_ip) {
        (window as any).__chatbotPublicIPv4 =
          data.public_ip;

        console.log(
          "[Client IP] Initialized:",
          data.public_ip,
        );
      }
    } catch (error) {
      console.error(
        "[Client IP] Failed to initialize:",
        error,
      );
    }
  };

  initializePublicIPv4();
}, []);
  /**
 * EN:
 * Track freedraw elements that were started locally.
 * The IP metadata is attached only after the stroke
 * has finished, so active drawing is not interrupted.
 *
 * VI:
 * Theo dõi các freedraw element được bắt đầu từ máy
 * hiện tại. Metadata IP chỉ được gắn sau khi stroke
 * hoàn thành để không làm gián đoạn quá trình vẽ.
 */
  const localFreedrawIdsRef = useRef<Set<string>>(
    new Set(),
  );
  // ============================================================
  // WHITEBOARD IMAGE SYNC
  // ============================================================

  // Images đã upload thành công
  const uploadedImageFileIdsRef =
    useRef<Set<FileId>>(new Set());

  // Images đang upload.
  // Dùng cái này để tránh onChange upload cùng image nhiều lần.
  const imageUploadsInFlightRef =
    useRef<Set<FileId>>(new Set());
  
  const whiteboardStateSyncTimerRef =
  useRef<ReturnType<typeof setTimeout> | null>(
    null,
  );
  // ============================================================
  // WHITEBOARD ACTION HISTORY
  // ============================================================

  const previousActionElementsRef =
    useRef<Map<string, WhiteboardElementSnapshot>>(
      new Map(),
    );

  const actionLogInitializedRef =
    useRef(false);

  const actionLogTimerRef =
    useRef<ReturnType<typeof setTimeout> | null>(
      null,
    );

    // ============================================================
  // SEND WHITEBOARD ACTION TO BACKEND
  // ============================================================

  const sendWhiteboardAction = (
    payload: WhiteboardActionPayload,
  ) => {
    void fetch(
      `${CHATBOT_BACKEND_URL}/api/whiteboard/action`,
      {
        method: "POST",

        headers: {
          "Content-Type": "application/json",
        },

        body: JSON.stringify(payload),
      },
    )
      .then(async (response) => {
        if (!response.ok) {
          console.error(
            "[Whiteboard Action] Failed:",
            response.status,
            await response.text(),
          );

          return;
        }

        console.log(
          "[Whiteboard Action]",
          payload.action,
          payload.element_id,
        );
      })
      .catch((error) => {
        console.error(
          "[Whiteboard Action] Request failed:",
          error,
        );
      });
  };


  // ============================================================
  // CREATE ACTION SNAPSHOT
  // ============================================================

  const createActionSnapshot = (
    element: OrderedExcalidrawElement,
  ): WhiteboardElementSnapshot => {
    return {
      id: element.id,
      type: element.type,

      x: element.x,
      y: element.y,

      width: element.width,
      height: element.height,

      angle: element.angle ?? 0,
      version: element.version ?? 0,

      isDeleted:
        element.isDeleted ?? false,
    };
  };


  // ============================================================
  // PROCESS WHITEBOARD ACTIONS
  // ============================================================

  const processWhiteboardActions = (
    elements:
      readonly OrderedExcalidrawElement[],
  ) => {
    const currentElements =
      new Map<
        string,
        WhiteboardElementSnapshot
      >();

    for (const element of elements) {
      const current =
        createActionSnapshot(element);

      currentElements.set(
        current.id,
        current,
      );

      const previous =
        previousActionElementsRef.current.get(
          current.id,
        );

      // CREATE
      if (!previous) {
        if (!current.isDeleted) {
          sendWhiteboardAction({
            action: "create",

            element_id: current.id,
            element_type: current.type,

            data: {
              x: current.x,
              y: current.y,

              width: current.width,
              height: current.height,

              angle: current.angle,
              version: current.version,
            },
          });
        }

        continue;
      }

      // DELETE
      if (
        !previous.isDeleted &&
        current.isDeleted
      ) {
        sendWhiteboardAction({
          action: "delete",

          element_id: current.id,
          element_type: current.type,

          data: {
            previous,
          },
        });

        continue;
      }

      if (
        current.isDeleted ||
        previous.isDeleted
      ) {
        continue;
      }

      // No change
      if (
        current.version ===
        previous.version
      ) {
        continue;
      }

      const moved =
        current.x !== previous.x ||
        current.y !== previous.y;

      const resized =
        current.width !== previous.width ||
        current.height !== previous.height;

      // RESIZE
      if (resized) {
        sendWhiteboardAction({
          action: "resize",

          element_id: current.id,
          element_type: current.type,

          data: {
            before: {
              x: previous.x,
              y: previous.y,

              width: previous.width,
              height: previous.height,
            },

            after: {
              x: current.x,
              y: current.y,

              width: current.width,
              height: current.height,
            },

            version: current.version,
          },
        });

        continue;
      }

      // MOVE
      if (moved) {
        sendWhiteboardAction({
          action: "move",

          element_id: current.id,
          element_type: current.type,

          data: {
            from: {
              x: previous.x,
              y: previous.y,
            },

            to: {
              x: current.x,
              y: current.y,
            },

            version: current.version,
          },
        });

        continue;
      }

      // OTHER UPDATE
      sendWhiteboardAction({
        action: "update",

        element_id: current.id,
        element_type: current.type,

        data: {
          version: current.version,
        },
      });
    }

    // Detect element removed completely
    for (
      const [previousId, previous]
      of previousActionElementsRef.current
    ) {
      if (
        !currentElements.has(previousId) &&
        !previous.isDeleted
      ) {
        sendWhiteboardAction({
          action: "delete",

          element_id: previous.id,
          element_type: previous.type,

          data: {
            previous,
          },
        });
      }
    }

    previousActionElementsRef.current =
      currentElements;
  };


  // ============================================================
  // TRACK WHITEBOARD ACTIONS
  // ============================================================

  const trackWhiteboardActions = (
    elements:
      readonly OrderedExcalidrawElement[],
  ) => {
    const snapshot = [...elements];

    // First call only establishes baseline.
    if (
      !actionLogInitializedRef.current
    ) {
      previousActionElementsRef.current =
        new Map(
          snapshot.map(
            (element) => [
              element.id,
              createActionSnapshot(element),
            ],
          ),
        );

      actionLogInitializedRef.current =
        true;

      console.log(
        "[Whiteboard Action] Initial snapshot:",
        snapshot.length,
        "element(s)",
      );

      return;
    }

    if (actionLogTimerRef.current) {
      clearTimeout(
        actionLogTimerRef.current,
      );
    }

    actionLogTimerRef.current =
      setTimeout(() => {
        actionLogTimerRef.current =
          null;

        processWhiteboardActions(
          snapshot,
        );
      }, 300);
  };

  // ============================================================
  // EQUATION GROUP -> PNG -> PADDLE OCR
  // ============================================================

  const equationPipelineRunningRef =
    useRef(false);

  const equationPipelinePendingRef =
    useRef(false);

  const syncEquationGroupsAndOcr =
    useCallback(async () => {
      if (!excalidrawAPI) {
        return;
      }

      // Avoid running multiple Paddle pipelines
      // at the same time.
      if (
        equationPipelineRunningRef.current
      ) {
        equationPipelinePendingRef.current =
          true;

        return;
      }

      equationPipelineRunningRef.current =
        true;

      try {
        do {
          equationPipelinePendingRef.current =
            false;

          // --------------------------------------------
          // 1. Ask backend to group strokes.
          // --------------------------------------------

          const groupResponse = await fetch(
            `${CHATBOT_BACKEND_URL}/api/equations/group`,
            {
              method: "POST",
            },
          );

          if (!groupResponse.ok) {
            throw new Error(
              `Equation grouping failed: ${groupResponse.status}`,
            );
          }

          const groupData =
            (await groupResponse.json()) as EquationGroupResponse;

          const equationGroups =
            Object.values(
              groupData.equations ?? {},
            );

          console.log(
            "[Equation Group]",
            `${equationGroups.length} group(s) found`,
          );

          // --------------------------------------------
          // 2. OCR each equation that does not already
          //    have a recognized equation.
          // --------------------------------------------

          for (const equation of equationGroups) {
            if (equation.equation) {
              console.log(
                "[Equation OCR] Already recognized:",
                equation.equation_id,
                equation.equation,
              );

              continue;
            }

            if (!equation.stroke_ids.length) {
              continue;
            }

            const strokeIdSet = new Set(
              equation.stroke_ids,
            );

            const equationElements =
              excalidrawAPI
                .getSceneElements()
                .filter((element) =>
                  strokeIdSet.has(element.id),
                );

            if (!equationElements.length) {
              console.warn(
                "[Equation OCR] No scene elements found:",
                equation.equation_id,
              );

              continue;
            }

            // ------------------------------------------
            // 3. Export ONLY this equation group
            //    as a PNG Blob.
            // ------------------------------------------

            const pngBlob =
              await exportToBlob({
                elements:
                  equationElements,

                appState: {
                  ...excalidrawAPI.getAppState(),

                  exportBackground:
                    true,

                  exportWithDarkMode:
                    false,

                  viewBackgroundColor:
                    "#ffffff",
                },

                files:
                  excalidrawAPI.getFiles(),

                mimeType:
                  "image/png",
              });

            console.log(
              "[Equation PNG]",
              equation.equation_id,
              `${pngBlob.size} bytes`,
            );

            // ------------------------------------------
            // 4. Send PNG to equation OCR endpoint.
            // ------------------------------------------

            const formData =
              new FormData();

            formData.append(
              "image",
              pngBlob,
              `${equation.equation_id}.png`,
            );

            const ocrResponse =
              await fetch(
                `${CHATBOT_BACKEND_URL}/api/equations/${encodeURIComponent(
                  equation.equation_id,
                )}/ocr`,
                {
                  method: "POST",
                  body: formData,
                },
              );

            if (!ocrResponse.ok) {
              const errorText =
                await ocrResponse.text();

              console.error(
                "[Equation OCR] Failed:",
                equation.equation_id,
                ocrResponse.status,
                errorText,
              );

              continue;
            }

            const ocrResult =
              await ocrResponse.json();

            console.log(
              "[Equation OCR] Recognized:",
              equation.equation_id,
              "->",
              ocrResult.equation,
            );
          }
          // --------------------------------------------
          // 5. Refresh tutoring hints after OCR
          // --------------------------------------------
          await refreshWhiteboardHints();

        } while (
          equationPipelinePendingRef.current
        );
      } catch (error) {
        console.error(
          "[Equation Pipeline] Failed:",
          error,
        );
      } finally {
        equationPipelineRunningRef.current =
          false;
      }
    }, [excalidrawAPI, refreshWhiteboardHints]);


  const scheduleEquationOcr =
    useCallback(() => {
      if (equationOcrTimerRef.current) {
        clearTimeout(
          equationOcrTimerRef.current,
        );
      }

      equationOcrTimerRef.current =
        setTimeout(() => {
          equationOcrTimerRef.current =
            null;

          void syncEquationGroupsAndOcr();
        }, 2000);
    }, [syncEquationGroupsAndOcr]);
  // ============================================================
  // STROKE JSON SYNC
  // ============================================================

  const equationOcrTimerRef =
    useRef<ReturnType<typeof setTimeout> | null>(
      null,
    );
  const strokeSyncTimerRef =
    useRef<ReturnType<typeof setTimeout> | null>(
      null,
    );

  const syncStrokesToBackend = useCallback(
    (
      elements:
        readonly OrderedExcalidrawElement[],
    ) => {
      if (strokeSyncTimerRef.current) {
        clearTimeout(
          strokeSyncTimerRef.current,
        );
      }

      const snapshot = [...elements];

      strokeSyncTimerRef.current =
        setTimeout(async () => {
          const strokes = snapshot.flatMap(
            (element) => {
              if (
                element.type !== "freedraw" ||
                element.isDeleted ||
                element.customData?.createdByAgent === true
              ) {
                return [];
              }

              return [
                {
                  stroke_id: element.id,

                  contributor_id:
                    element.customData
                      ?.createdByContributorId ??
                    null,

                  created_by_ip:
                    element.customData
                      ?.createdByIp ??
                    null,

                  x: element.x,
                  y: element.y,

                  width: element.width,
                  height: element.height,

                  points:
                    element.points.map(
                      (point) =>
                        Array.from(point),
                    ),

                  is_deleted: false,
                }
              ];
            },
          );

          try {
            const response = await fetch(
              `${CHATBOT_BACKEND_URL}/api/strokes/sync`,
              {
                method: "POST",

                headers: {
                  "Content-Type":
                    "application/json",
                },

                body: JSON.stringify({
                  strokes,
                }),
              },
            );

            if (!response.ok) {
              throw new Error(
                `Stroke sync failed: ${response.status}`,
              );
            }

            console.log(
              "[Stroke Sync]",
              `${strokes.length} stroke(s) saved`,
            );
            if (strokes.length > 0) {
              scheduleEquationOcr();
            }
            
          } catch (error) {
            console.error(
              "[Stroke Sync] Failed:",
              error,
            );
          }
        }, 500);
    },
    [scheduleEquationOcr],
  );

  useEffect(() => {
    const script = document.createElement("script");

    script.type = "module";
    script.src = CHATBOT_WIDGET_SRC;
      

    document.body.appendChild(script);

    return () => {
      script.remove();
    };
  }, []);

  // ============================================================
  // JARVIS HANDWRITING ANIMATION QUEUE
  // ============================================================

  const handwritingQueueRef = useRef<Promise<void>>(
      Promise.resolve(),
    );
  /**
   * EN:
   * Expose the minimum Excalidraw functionality required by the
   * external chatbot. The chatbot can read the current scene and
   * export selected elements as a PNG image.
   *
   * VI:
   * Cung cấp các chức năng Excalidraw tối thiểu mà chatbot bên ngoài
   * cần sử dụng. Chatbot có thể đọc scene hiện tại và export các
   * element được chọn thành ảnh PNG.
   */
  useEffect(() => {
    if (!excalidrawAPI) {
      return;
    }

    
    const bridge = {
      /**
       * EN:
       * Return the current non-deleted Excalidraw elements.
       *
       * VI:
       * Trả về các element hiện tại trên Excalidraw chưa bị xóa.
       */
      getScene() {
        return {
          elements: excalidrawAPI.getSceneElements(),
          appState: excalidrawAPI.getAppState(),
          files: excalidrawAPI.getFiles(),
        };
      },

      addEllipse({
        x,
        y,
        width,
        height,
      }: {
        x: number;
        y: number;
        width: number;
        height: number;
      }) {
        const currentElements =
          excalidrawAPI.getSceneElements();

        const [ellipse] =
          convertToExcalidrawElements([
            {
              type: "ellipse",
              x,
              y,
              width,
              height,
              strokeColor: "#e03131",
              backgroundColor: "transparent",
              fillStyle: "solid",
              strokeWidth: 1,
              strokeStyle: "solid",
              roughness: 1,
              opacity: 100,
            },
          ]);

        excalidrawAPI.updateScene({
          elements: [
            ...currentElements,
            ellipse,
          ],
          captureUpdate:
            CaptureUpdateAction.NEVER,
        });

        console.log(
          "[Chatbot] Added ellipse:",
          ellipse,
        );

        return ellipse;
      },

      
      
      writeMath({
        expression,
        x,
        y,
        anchorElementIds,
        solutionGroupId,
        actionId,
      }: {
        expression: string;
        x?: number;
        y?: number;
        anchorElementIds?: string[];
        solutionGroupId?: string;
        actionId?: string;
      }) {
        const run = async () => {
          // 1. Validate input
          if (!expression?.trim()) {
            throw new Error("Math expression is empty.");
          }

          if ((x === undefined) !== (y === undefined)) {
            throw new Error(
              "Provide both x and y, or neither.",
            );
          }

          if (
            x !== undefined &&
            (!Number.isFinite(x) || !Number.isFinite(y))
          ) {
            throw new Error("Invalid coordinates.");
          }

          // 2. Read the latest scene inside the queue
          const currentElements =
            excalidrawAPI.getSceneElements();

          const { width, height } =
            measureMathExpression(expression);

          if (!(width > 0 && height > 0)) {
            throw new Error("Invalid math dimensions.");
          }

          // 3. Collision detection
          const padding = 16;

          const collides = (px: number, py: number) =>
            currentElements.some(
              (element) =>
                !element.isDeleted &&
                px < element.x + element.width + padding &&
                px + width + padding > element.x &&
                py < element.y + element.height + padding &&
                py + height + padding > element.y,
            );

          // 4. Determine placement
          let position: { x: number; y: number };

          if (x !== undefined && y !== undefined) {
            position = { x, y };

            if (collides(x, y)) {
              throw new Error(
                "Requested position overlaps existing elements.",
              );
            }
          } else if (anchorElementIds?.length) {
            const anchorIds = new Set(anchorElementIds);

            const anchors = currentElements.filter(
              (element) =>
                !element.isDeleted &&
                anchorIds.has(element.id),
            );

            if (anchors.length !== anchorIds.size) {
              throw new Error(
                "Some anchor elements are missing from the scene.",
              );
            }

            const left = Math.min(
              ...anchors.map((element) => element.x),
            );

            const bottom = Math.max(
              ...anchors.map(
                (element) => element.y + element.height,
              ),
            );

            position = {
              x: left,
              y: bottom + 24,
            };

            let attempts = 0;

            while (
              collides(position.x, position.y) &&
              attempts < 100
            ) {
              position.y += Math.max(
                height + padding,
                24,
              );
              attempts++;
            }

            if (collides(position.x, position.y)) {
              throw new Error(
                "No free space below anchor elements.",
              );
            }
          } else {
            position = findAvailablePosition(
              currentElements,
              width,
              height,
            );

            if (collides(position.x, position.y)) {
              throw new Error(
                "Automatic placement overlaps existing elements.",
              );
            }
          }

          // 5. Generate native freedraw strokes
          const rawStrokes = expressionToFreedraw(
            expression,
            position.x,
            position.y,
          );

          if (!rawStrokes.length) {
            throw new Error(
              "Expression generated no drawing strokes.",
            );
          }

          
          
          
          
          const converted = convertToExcalidrawElements(
            rawStrokes.map((stroke) => ({
              ...stroke,
              type: "freedraw" as const,
            })) as unknown as NonNullable<
              Parameters<typeof convertToExcalidrawElements>[0]
            >,
          );





          if (!converted.length) {
            throw new Error(
              "Failed to create Excalidraw elements.",
            );
          }

          // 6. Normalize elements and attach metadata
          const mathElements = converted.map((element) => ({
            ...element,
            version:
              Number.isInteger(element.version) &&
              element.version >= 0
                ? element.version
                : 1,
            versionNonce: Number.isInteger(
              element.versionNonce,
            )
              ? element.versionNonce
              : Math.floor(Math.random() * 2 ** 31),
            isDeleted: false as const,
            customData: {
              ...element.customData,
              createdByAgent: true,
              agentSolutionGroupId: solutionGroupId ?? null,
              agentActionId: actionId ?? null,
            },
          }));

          const invalidElements = mathElements.filter(
            (element) =>
              !Number.isInteger(element.version) ||
              element.version < 0 ||
              !Number.isInteger(element.versionNonce),
          );

          if (invalidElements.length > 0) {
            throw new Error(
              "Generated elements have invalid versions.",
            );
          }

          const elementIds = mathElements.map(
            (element) => element.id,
          );

          const allIds = [
            ...excalidrawAPI
              .getSceneElementsIncludingDeleted()
              .map((element) => element.id),
            ...elementIds,
          ];

          if (new Set(allIds).size !== allIds.length) {
            throw new Error(
              "Duplicate Excalidraw element IDs detected.",
            );
          }

          // 7. Get the overlay container
          const container = hintOverlayRootRef.current;

          if (!container) {
            throw new Error(
              "Handwriting overlay container is missing.",
            );
          }

          // 8. Animate handwriting, then commit
          await animateMathHandwriting({
            container,

            strokes: mathElements.map((element) => {
              if (element.type !== "freedraw") {
                throw new Error(
                  "Expected freedraw element.",
                );
              }

              return {
                x: element.x,
                y: element.y,
                points: element.points.map(
                  (point) =>
                    [point[0], point[1]] as const,
                ),
                strokeColor: element.strokeColor,
                strokeWidth: element.strokeWidth,
              };
            }),

            getViewport: () => {
              const state = excalidrawAPI.getAppState();

              return {
                scrollX: state.scrollX,
                scrollY: state.scrollY,
                zoom: Number(state.zoom?.value ?? 1),
                offsetLeft: state.offsetLeft ?? 0,
                offsetTop: state.offsetTop ?? 0,
              };
            },

            durationPerStroke: 180,

            // Called while SVG overlay is still visible.
            onComplete: () => {
              const latestElements =
                excalidrawAPI
                  .getSceneElementsIncludingDeleted();

              const latestIds = new Set(
                latestElements.map(
                  (element) => element.id,
                ),
              );

              if (
                elementIds.some((id) => latestIds.has(id))
              ) {
                throw new Error(
                  "Generated element IDs already exist.",
                );
              }

              excalidrawAPI.updateScene({
                elements: [
                  ...latestElements,
                  ...mathElements,
                ],
                captureUpdate:
                  CaptureUpdateAction.IMMEDIATELY,
              });
            },
          });

          // 9. Verify committed elements
          const sceneIds = new Set(
            excalidrawAPI
              .getSceneElements()
              .map((element) => element.id),
          );

          const success = elementIds.every(
            (id) => sceneIds.has(id),
          );

          return {
            success,
            expression,
            element_ids: elementIds,
            position,
            width,
            height,
            error: success
              ? null
              : "Generated elements not found in scene.",
          };
        };

        // 10. Queue each handwriting request
        const pending =
          handwritingQueueRef.current.then(run);

        // Keep the queue alive even if one request fails.
        handwritingQueueRef.current = pending.then(
          () => undefined,
          () => undefined,
        );

        return pending;
      },



      async exportWhiteboardToPng() {
        const elements =
          excalidrawAPI.getSceneElements();

        if (!elements.length) {
          return null;
        }

        return await exportToBlob({
          elements,

          appState: {
            ...excalidrawAPI.getAppState(),
            exportBackground: true,
            exportWithDarkMode: false,
            viewBackgroundColor: "#ffffff",
          },

          files: excalidrawAPI.getFiles(),

          mimeType: "image/png",
        });
      },

      /**
       * EN:
       * Export a selected group of Excalidraw elements as a PNG Blob.
       *
       * VI:
       * Export một nhóm Excalidraw element được chọn thành PNG Blob.
       */
      async exportElementsToPng(elementIds: string[]) {
        const idSet = new Set(elementIds);

        const elements = excalidrawAPI
          .getSceneElements()
          .filter((element) => idSet.has(element.id));

        if (!elements.length) {
          return null;
        }

        return await exportToBlob({
          elements,
          appState: {
            ...excalidrawAPI.getAppState(),
            exportBackground: true,
            exportWithDarkMode: false,
            viewBackgroundColor: "#ffffff",
          },
          files: excalidrawAPI.getFiles(),
          mimeType: "image/png",
        });
      },
    };

    (window as any).__excalidrawChatbotBridge = bridge;

    return () => {
      if ((window as any).__excalidrawChatbotBridge === bridge) {
        delete (window as any).__excalidrawChatbotBridge;
      }
    };
  }, [excalidrawAPI]);

  const [errorMessage, setErrorMessage] = useState("");
  const isCollabDisabled = isRunningInIframe();

  const { editorTheme, appTheme, setAppTheme } = useHandleAppTheme();

  const [langCode, setLangCode] = useAppLangCode();

  const editorInterface = useEditorInterface();

  // initial state
  // ---------------------------------------------------------------------------

  const initialStatePromiseRef = useRef<{
    promise: ResolvablePromise<ExcalidrawInitialDataState | null>;
  }>({ promise: null! });
  if (!initialStatePromiseRef.current.promise) {
    initialStatePromiseRef.current.promise =
      resolvablePromise<ExcalidrawInitialDataState | null>();
  }

  const debugCanvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    trackEvent("load", "frame", getFrame());
    // Delayed so that the app has a time to load the latest SW
    setTimeout(() => {
      trackEvent("load", "version", getVersion());
    }, VERSION_TIMEOUT);
  }, []);

  const [, setShareDialogState] = useAtom(shareDialogStateAtom);
  const [collabAPI] = useAtom(collabAPIAtom);
  const [isCollaborating] = useAtomWithInitialValue(isCollaboratingAtom, () => {
    return isCollaborationLink(window.location.href);
  });

  // ============================================================
  // ROOM PRESENCE
  // ============================================================

  const presenceSessionIdRef =
    useRef<string | null>(null);

  useEffect(() => {
    // Only track presence while the user
    // is actually inside a collaboration room.
    if (!isCollaborating) {
      return;
    }

    const sessionId =
      crypto.randomUUID();

    presenceSessionIdRef.current =
      sessionId;

    console.log(
      "[Presence] Session ID:",
      sessionId,
    );

    const joinRoom = async () => {
      try {
        const response = await fetch(
          `${CHATBOT_BACKEND_URL}/api/presence/join?session_id=${encodeURIComponent(
            sessionId,
          )}`,
          {
            method: "POST",
          },
        );

        if (!response.ok) {
          throw new Error(
            `Presence join failed: ${response.status}`,
          );
        }

        const result =
          await response.json();

        console.log(
          "[Presence] Joined:",
          result,
        );
      } catch (error) {
        console.error(
          "[Presence] Join failed:",
          error,
        );
      }
    };


    const sendHeartbeat =
      async () => {
        try {
          const response = await fetch(
            `${CHATBOT_BACKEND_URL}/api/presence/heartbeat?session_id=${encodeURIComponent(
              sessionId,
            )}`,
            {
              method: "POST",
            },
          );

          if (!response.ok) {
            throw new Error(
              `Presence heartbeat failed: ${response.status}`,
            );
          }

          console.log(
            "[Presence] Heartbeat:",
            sessionId,
          );
        } catch (error) {
          console.error(
            "[Presence] Heartbeat failed:",
            error,
          );
        }
      };


    // JOIN immediately
    void joinRoom();


    // HEARTBEAT every 10 seconds
    const heartbeatTimer =
      window.setInterval(
        () => {
          void sendHeartbeat();
        },
        10000,
      );


    return () => {
      window.clearInterval(
        heartbeatTimer,
      );

      presenceSessionIdRef.current =
        null;
    };
  }, [isCollaborating]);
  const collabError = useAtomValue(collabErrorIndicatorAtom);
  const userToFollow = useAtomValue(userToFollowAtom);

  const viewportStatusFrame = useMemo(
    () =>
      userToFollow
        ? {
            border: "var(--color-primary-hover)",
            label: {
              label: (
                <>
                  Following{" "}
                  <span
                    style={{
                      display: "block",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      maxWidth: 100,
                    }}
                    title={userToFollow.username}
                  >
                    {userToFollow.username}
                  </span>
                </>
              ),
              onClose: () => collabAPI?.setUserToFollow(null),
            },
          }
        : null,
    [userToFollow, collabAPI],
  );

  useHandleLibrary({
    excalidrawAPI,
    adapter: LibraryIndexedDBAdapter,
    // TODO maybe remove this in several months (shipped: 24-03-11)
    migrationAdapter: LibraryLocalStorageMigrationAdapter,
  });

  const [, forceRefresh] = useState(false);

  useEffect(() => {
    if (isDevEnv()) {
      const debugState = loadSavedDebugState();

      if (debugState.enabled && !window.visualDebug) {
        window.visualDebug = {
          data: [],
        };
      } else {
        delete window.visualDebug;
      }
      forceRefresh((prev) => !prev);
    }
  }, [excalidrawAPI]);

  // ?collaborators=<N> — populate the canvas with N static fake
  // collaborators for exercising avatar/UserList UI without a real
  // collab room
  useSimulatedCollaborators(excalidrawAPI);

  // ---------------------------------------------------------------------------
  // Hoisted loadImages
  // ---------------------------------------------------------------------------
  const loadImages = useCallback(
    (data: ResolutionType<typeof initializeScene>, isInitialLoad = false) => {
      if (!data.scene || !excalidrawAPI) {
        return;
      }

      if (collabAPI?.isCollaborating()) {
        if (data.scene.elements) {
          collabAPI
            .fetchImageFilesFromFirebase({
              elements: data.scene.elements,
              forceFetchFiles: true,
            })
            .then(({ loadedFiles, erroredFiles }) => {
              excalidrawAPI.addFiles(loadedFiles);
              updateStaleImageStatuses({
                excalidrawAPI,
                erroredFiles,
                elements: excalidrawAPI.getSceneElementsIncludingDeleted(),
              });
            });
        }
      } else {
        const fileIds =
          data.scene.elements?.reduce((acc, element) => {
            if (isInitializedImageElement(element)) {
              return acc.concat(element.fileId);
            }
            return acc;
          }, [] as FileId[]) || [];

        if (data.isExternalScene) {
          if (fileIds.length) {
            // Direct Firebase call (not through FileManager), so track manually
            FileStatusStore.updateStatuses(
              fileIds.map((id) => [id, "loading"]),
            );
          }
          loadFilesFromFirebase(
            `${FIREBASE_STORAGE_PREFIXES.shareLinkFiles}/${data.id}`,
            data.key,
            fileIds,
          ).then(({ loadedFiles, erroredFiles }) => {
            excalidrawAPI.addFiles(loadedFiles);
            updateStaleImageStatuses({
              excalidrawAPI,
              erroredFiles,
              elements: excalidrawAPI.getSceneElementsIncludingDeleted(),
            });
            FileStatusStore.updateStatuses([
              ...loadedFiles.map((f) => [f.id, "loaded"] as [FileId, "loaded"]),
              ...[...erroredFiles.keys()].map(
                (id) => [id, "error"] as [FileId, "error"],
              ),
            ]);
          });
        } else if (isInitialLoad) {
          if (fileIds.length) {
            LocalData.fileStorage
              .getFiles(fileIds)
              .then(async ({ loadedFiles, erroredFiles }) => {
                if (loadedFiles.length) {
                  excalidrawAPI.addFiles(loadedFiles);
                }
                updateStaleImageStatuses({
                  excalidrawAPI,
                  erroredFiles,
                  elements: excalidrawAPI.getSceneElementsIncludingDeleted(),
                });
              });
          }
          // on fresh load, clear unused files from IDB (from previous
          // session)
          LocalData.fileStorage.clearObsoleteFiles({
            currentFileIds: fileIds,
          });
        }
      }
    },
    [collabAPI, excalidrawAPI],
  );

  useEffect(() => {
    if (!excalidrawAPI || (!isCollabDisabled && !collabAPI)) {
      return;
    }

    initializeScene({ collabAPI, excalidrawAPI }).then(async (data) => {
      loadImages(data, /* isInitialLoad */ true);
      initialStatePromiseRef.current.promise.resolve(data.scene);
    });

    const onHashChange = async (event: HashChangeEvent) => {
      event.preventDefault();
      const libraryUrlTokens = parseLibraryTokensFromUrl();
      if (!libraryUrlTokens) {
        if (
          collabAPI?.isCollaborating() &&
          !isCollaborationLink(window.location.href)
        ) {
          collabAPI.stopCollaboration(false);
        }
        excalidrawAPI.updateScene({ appState: { isLoading: true } });

        initializeScene({ collabAPI, excalidrawAPI }).then((data) => {
          loadImages(data);
          if (data.scene) {
            excalidrawAPI.updateScene({
              elements: restoreElements(data.scene.elements, null, {
                repairBindings: true,
              }),
              appState: restoreAppState(data.scene.appState, null),
              captureUpdate: CaptureUpdateAction.IMMEDIATELY,
            });
          }
        });
      }
    };

    const syncData = debounce(() => {
      if (isTestEnv()) {
        return;
      }
      if (
        !document.hidden &&
        ((collabAPI && !collabAPI.isCollaborating()) || isCollabDisabled)
      ) {
        // don't sync if local state is newer or identical to browser state
        if (isBrowserStorageStateNewer(STORAGE_KEYS.VERSION_DATA_STATE)) {
          const localDataState = importFromLocalStorage();
          const username = importUsernameFromLocalStorage();
          setLangCode(getPreferredLanguage());
          excalidrawAPI.updateScene({
            ...localDataState,
            captureUpdate: CaptureUpdateAction.NEVER,
          });
          LibraryIndexedDBAdapter.load().then((data) => {
            if (data) {
              excalidrawAPI.updateLibrary({
                libraryItems: data.libraryItems,
              });
            }
          });
          collabAPI?.setUsername(username || "");
        }

        if (isBrowserStorageStateNewer(STORAGE_KEYS.VERSION_FILES)) {
          const elements = excalidrawAPI.getSceneElementsIncludingDeleted();
          const currFiles = excalidrawAPI.getFiles();
          const fileIds =
            elements?.reduce((acc, element) => {
              if (
                isInitializedImageElement(element) &&
                // only load and update images that aren't already loaded
                !currFiles[element.fileId]
              ) {
                return acc.concat(element.fileId);
              }
              return acc;
            }, [] as FileId[]) || [];
          if (fileIds.length) {
            LocalData.fileStorage
              .getFiles(fileIds)
              .then(({ loadedFiles, erroredFiles }) => {
                if (loadedFiles.length) {
                  excalidrawAPI.addFiles(loadedFiles);
                }
                updateStaleImageStatuses({
                  excalidrawAPI,
                  erroredFiles,
                  elements: excalidrawAPI.getSceneElementsIncludingDeleted(),
                });
              });
          }
        }
      }
    }, SYNC_BROWSER_TABS_TIMEOUT);

    const onUnload = () => {
      LocalData.flushSave();
    };

    const visibilityChange = (event: FocusEvent | Event) => {
      if (event.type === EVENT.BLUR || document.hidden) {
        LocalData.flushSave();
      }
      if (
        event.type === EVENT.VISIBILITY_CHANGE ||
        event.type === EVENT.FOCUS
      ) {
        syncData();
      }
    };

    window.addEventListener(EVENT.HASHCHANGE, onHashChange, false);
    window.addEventListener(EVENT.UNLOAD, onUnload, false);
    window.addEventListener(EVENT.BLUR, visibilityChange, false);
    document.addEventListener(EVENT.VISIBILITY_CHANGE, visibilityChange, false);
    window.addEventListener(EVENT.FOCUS, visibilityChange, false);
    return () => {
      window.removeEventListener(EVENT.HASHCHANGE, onHashChange, false);
      window.removeEventListener(EVENT.UNLOAD, onUnload, false);
      window.removeEventListener(EVENT.BLUR, visibilityChange, false);
      window.removeEventListener(EVENT.FOCUS, visibilityChange, false);
      document.removeEventListener(
        EVENT.VISIBILITY_CHANGE,
        visibilityChange,
        false,
      );
    };
  }, [isCollabDisabled, collabAPI, excalidrawAPI, setLangCode, loadImages]);

  useEffect(() => {
    const unloadHandler = (event: BeforeUnloadEvent) => {
      LocalData.flushSave();

      if (
        excalidrawAPI &&
        LocalData.fileStorage.shouldPreventUnload(
          excalidrawAPI.getSceneElements(),
        )
      ) {
        if (import.meta.env.VITE_APP_DISABLE_PREVENT_UNLOAD !== "true") {
          preventUnload(event);
        } else {
          console.warn(
            "preventing unload disabled (VITE_APP_DISABLE_PREVENT_UNLOAD)",
          );
        }
      }
    };
    window.addEventListener(EVENT.BEFORE_UNLOAD, unloadHandler);
    return () => {
      window.removeEventListener(EVENT.BEFORE_UNLOAD, unloadHandler);
    };
  }, [excalidrawAPI]);


  // ============================================================
  // SYNC INSERTED IMAGES TO CHATBOT BACKEND
  // ============================================================

  const syncImagesToBackend = useCallback(
    async (
      elements: readonly OrderedExcalidrawElement[],
      files: BinaryFiles,
    ) => {
      for (const element of elements) {
        // Chỉ xử lý image đã được Excalidraw initialize
        if (
          !isInitializedImageElement(element) ||
          element.isDeleted
        ) {
          continue;
        }

        const fileId = element.fileId;

        // Đã upload rồi -> bỏ qua
        if (
          uploadedImageFileIdsRef.current.has(fileId)
        ) {
          continue;
        }

        // Đang upload -> bỏ qua để tránh duplicate request
        if (
          imageUploadsInFlightRef.current.has(fileId)
        ) {
          continue;
        }

        const imageFile = files[fileId];

        // Image data chưa available
        if (!imageFile?.dataURL) {
          continue;
        }

        imageUploadsInFlightRef.current.add(fileId);

        try {
          // ----------------------------------------------------
          // 1. Convert Excalidraw dataURL -> actual binary Blob
          // ----------------------------------------------------

          const blobResponse = await fetch(
            imageFile.dataURL,
          );

          if (!blobResponse.ok) {
            throw new Error(
              `Could not convert image ${fileId} to Blob`,
            );
          }

          const blob = await blobResponse.blob();

          // ----------------------------------------------------
          // 2. Determine file extension
          // ----------------------------------------------------

          let extension = "png";

          switch (imageFile.mimeType) {
            case "image/jpeg":
              extension = "jpg";
              break;

            case "image/webp":
              extension = "webp";
              break;

            case "image/svg+xml":
              extension = "svg";
              break;

            case "image/png":
            default:
              extension = "png";
              break;
          }

          // ----------------------------------------------------
          // 3. Build multipart/form-data
          // ----------------------------------------------------

          const formData = new FormData();

          formData.append(
            "image",
            blob,
            `${fileId}.${extension}`,
          );

          formData.append(
            "file_id",
            fileId,
          );

          formData.append(
            "element_id",
            element.id,
          );

          formData.append(
            "mime_type",
            imageFile.mimeType,
          );

          formData.append(
            "x",
            String(element.x),
          );

          formData.append(
            "y",
            String(element.y),
          );

          formData.append(
            "width",
            String(element.width),
          );

          formData.append(
            "height",
            String(element.height),
          );

          // ----------------------------------------------------
          // 4. Send actual image to FastAPI
          // ----------------------------------------------------

          const response = await fetch(
            `${CHATBOT_BACKEND_URL}/api/whiteboard/images`,
            {
              method: "POST",
              body: formData,
            },
          );

          if (!response.ok) {
            const errorText =
              await response.text();

            throw new Error(
              `Image upload failed: ${response.status} ${errorText}`,
            );
          }

          const result =
            await response.json();

          // ----------------------------------------------------
          // 5. Mark successful
          // ----------------------------------------------------

          uploadedImageFileIdsRef.current.add(
            fileId,
          );

          console.log(
            "[Whiteboard Image] Uploaded:",
            {
              elementId: element.id,
              fileId,
              mimeType: imageFile.mimeType,
              backend: result,
            },
          );
        } catch (error) {
          console.error(
            "[Whiteboard Image] Upload failed:",
            fileId,
            error,
          );
        } finally {
          imageUploadsInFlightRef.current.delete(
            fileId,
          );
        }
      }
    },
    [],
  );

  const syncWhiteboardStateToBackend =
  useCallback(
    async (
      elements:
        readonly OrderedExcalidrawElement[],
      appState: AppState,
    ) => {
      const currentElements =
        elements.filter(
          (element) =>
            !element.isDeleted,
        );

      console.log(
        "[Whiteboard State] Sending:",
        currentElements.length,
        currentElements,
      );

      const payload = {
        elements: currentElements,

        app_state: {
          scrollX:
            appState.scrollX,

          scrollY:
            appState.scrollY,

          zoom:
            appState.zoom?.value ?? 1,

          viewBackgroundColor:
            appState.viewBackgroundColor,
        },
      };

      try {
        const response =
          await fetch(
            `${CHATBOT_BACKEND_URL}/api/whiteboard/state`,
            {
              method: "POST",

              headers: {
                "Content-Type":
                  "application/json",
              },

              body:
                JSON.stringify(
                  payload,
                ),
            },
          );

        if (!response.ok) {
          const errorText =
            await response.text();

          throw new Error(
            `Whiteboard state sync failed: ${response.status} ${errorText}`,
          );
        }

        const result =
          await response.json();

        console.log(
          "[Whiteboard State] Synced:",
          result,
        );
      } catch (error) {
        console.error(
          "[Whiteboard State] Sync failed:",
          error,
        );
      }
    },
    [],
  );
  const onChange = (
    elements:
      readonly OrderedExcalidrawElement[],
    appState: AppState,
    files: BinaryFiles,
  ) => {
    // ============================================================
    // UPDATE WHITEBOARD HINT VIEWPORT
    // ============================================================

    const nextHintViewport: HintViewport = {
      scrollX: appState.scrollX,
      scrollY: appState.scrollY,
      zoom: Number(appState.zoom?.value ?? 1),
      offsetLeft: appState.offsetLeft ?? 0,
      offsetTop: appState.offsetTop ?? 0,
    };

    setHintViewport((previous) => {
      if (
        previous.scrollX === nextHintViewport.scrollX &&
        previous.scrollY === nextHintViewport.scrollY &&
        previous.zoom === nextHintViewport.zoom &&
        previous.offsetLeft === nextHintViewport.offsetLeft &&
        previous.offsetTop === nextHintViewport.offsetTop
      ) {
        return previous;
      }

      return nextHintViewport;
    });
    const publicIPv4 =
      (window as any)
        .__chatbotPublicIPv4 as
        | string
        | undefined;
    
    const contributorId =
      contributorIdRef.current;

    let nextElements = elements;
    let didTagStroke = false;


    // ============================================================
    // 1. TRACK LOCAL FREEDRAW WHILE DRAWING
    // ============================================================

    if (
      appState.newElement?.type ===
        "freedraw"
    ) {
      localFreedrawIdsRef.current.add(
        appState.newElement.id,
      );
    }


    // ============================================================
    // 2. TAG FINISHED LOCAL STROKE WITH IP
    // ============================================================

    if (
      !appState.newElement &&
      localFreedrawIdsRef.current.size > 0
    ) {
      nextElements = elements.map(
        (element) => {
          if (
            element.type !==
              "freedraw" ||
            !localFreedrawIdsRef.current.has(
              element.id,
            ) ||
            element.customData
              ?.createdByContributorId
          ) {
            return element;
          }

          didTagStroke = true;

          localFreedrawIdsRef.current.delete(
            element.id,
          );

          return newElementWith(
            element,
            {
              customData: {
                ...element.customData,

                createdByContributorId:
                  contributorId,

                ...(publicIPv4
                  ? {
                      createdByIp:
                        publicIPv4,
                    }
                  : {}),
              },
            },
          );
        },
      );

      if (
        didTagStroke &&
        excalidrawAPI
      ) {
        excalidrawAPI.updateScene({
          elements: nextElements,

          captureUpdate:
            CaptureUpdateAction.NEVER,
        });
      }
    }


    // ============================================================
    // 3. LOG WHITEBOARD ACTION HISTORY
    // ============================================================

    if (!appState.newElement) {
      trackWhiteboardActions(
        nextElements,
      );
    }
    // ============================================================
    // 4. SYNC ELEMENTS TO LIVE COLLABORATION
    // ============================================================

    if (
      collabAPI?.isCollaborating()
    ) {
      collabAPI.syncElements(
        nextElements,
      );
    }


    // ============================================================
    // 5. SAVE FINISHED STROKES TO strokes.json
    // ============================================================

    if (!appState.newElement) {
      syncStrokesToBackend(
        nextElements,
      );
    }

    // ============================================================
    // 6. SYNC INSERTED IMAGES TO CHATBOT BACKEND
    // ============================================================

    void syncImagesToBackend(
      nextElements,
      files,
    );
    // ============================================================
    // 7. SYNC CURRENT WHITEBOARD STATE TO CHATBOT BACKEND
    // ============================================================

    syncWhiteboardStateToBackend(
      nextElements,
      appState,
    );

    // ============================================================
    // 8. EXISTING LOCAL EXCALIDRAW SAVE
    // ============================================================

    

    if (!LocalData.isSavePaused()) {
      LocalData.save(
        nextElements,
        appState,
        files,
        () => {
          if (excalidrawAPI) {
            let didChange = false;

            const savedElements =
              excalidrawAPI
                .getSceneElementsIncludingDeleted()
                .map((element) => {
                  if (
                    LocalData.fileStorage
                      .shouldUpdateImageElementStatus(
                        element,
                      )
                  ) {
                    const newElement =
                      newElementWith(
                        element,
                        {
                          status:
                            "saved",
                        },
                      );

                    if (
                      newElement !==
                      element
                    ) {
                      didChange = true;
                    }

                    return newElement;
                  }

                  return element;
                });

            if (didChange) {
              excalidrawAPI.updateScene({
                elements:
                  savedElements,

                captureUpdate:
                  CaptureUpdateAction.NEVER,
              });
            }
          }
        },
      );
    }


    if (
      debugCanvasRef.current &&
      excalidrawAPI
    ) {
      debugRenderer(
        debugCanvasRef.current,
        appState,
        nextElements,
        window.devicePixelRatio,
      );
    }
  };


  const [latestShareableLink, setLatestShareableLink] = useState<string | null>(
    null,
  );

  const onExportToBackend = async (
    exportedElements: readonly NonDeletedExcalidrawElement[],
    appState: Partial<AppState>,
    files: BinaryFiles,
  ) => {
    if (exportedElements.length === 0) {
      throw new Error(t("alerts.cannotExportEmptyCanvas"));
    }
    try {
      const { url, errorMessage } = await exportToBackend(
        exportedElements,
        {
          ...appState,
          viewBackgroundColor: appState.exportBackground
            ? appState.viewBackgroundColor
            : getDefaultAppState().viewBackgroundColor,
        },
        files,
      );

      if (errorMessage) {
        throw new Error(errorMessage);
      }

      if (url) {
        setLatestShareableLink(url);
      }
    } catch (error: any) {
      if (error.name !== "AbortError") {
        const { width, height } = appState;
        console.error(error, {
          width,
          height,
          devicePixelRatio: window.devicePixelRatio,
        });
        throw new Error(error.message);
      }
    }
  };

  const renderCustomStats = (
    elements: readonly NonDeletedExcalidrawElement[],
    appState: UIAppState,
  ) => {
    return (
      <CustomStats
        setToast={(message) => excalidrawAPI!.setToast({ message })}
        appState={appState}
        elements={elements}
      />
    );
  };

  const isOffline = useAtomValue(isOfflineAtom);

  const localStorageQuotaExceeded = useAtomValue(localStorageQuotaExceededAtom);

  const onCollabDialogOpen = useCallback(
    () => setShareDialogState({ isOpen: true, type: "collaborationOnly" }),
    [setShareDialogState],
  );

  // ---------------------------------------------------------------------------
  // onExport — intercepts file save to wait for pending image loads
  // ---------------------------------------------------------------------------
  const onExport: Required<ExcalidrawProps>["onExport"] = useCallback(
    async function* () {
      let snapshot = FileStatusStore.getSnapshot();
      const { pending, total } = FileStatusStore.getPendingCount(
        snapshot.value,
      );
      if (pending === 0) {
        return;
      }

      // Yield initial progress
      yield {
        type: "progress",
        progress: (total - pending) / total,
        message: `Loading images (${total - pending}/${total})...`,
      };

      // Wait for all pending images to finish
      while (true) {
        snapshot = await FileStatusStore.pull(snapshot.version);
        const { pending: nowPending, total: nowTotal } =
          FileStatusStore.getPendingCount(snapshot.value);

        yield {
          type: "progress",
          progress: (nowTotal - nowPending) / nowTotal,
          message: `Loading images (${nowTotal - nowPending}/${nowTotal})...`,
        };

        if (nowPending === 0) {
          await new Promise((r) => setTimeout(r, 500));
          yield {
            type: "progress",
            message: `Preparing export...`,
          };
          return;
        }
      }
    },
    [],
  );

  // const onExport = () => {
  //   return new Promise((r) => setTimeout(r, 2500));
  //   // console.log("onExport");
  // };

  // browsers generally prevent infinite self-embedding, there are
  // cases where it still happens, and while we disallow self-embedding
  // by not whitelisting our own origin, this serves as an additional guard
  if (isSelfEmbedding) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          textAlign: "center",
          height: "100%",
        }}
      >
        <h1>I'm not a pretzel!</h1>
      </div>
    );
  }

  const ExcalidrawPlusCommand = {
    label: "Excalidraw+",
    category: DEFAULT_CATEGORIES.links,
    predicate: true,
    icon: <div style={{ width: 14 }}>{ExcalLogo}</div>,
    keywords: ["plus", "cloud", "server"],
    perform: () => {
      window.open(
        `${
          import.meta.env.VITE_APP_PLUS_LP
        }/plus?utm_source=excalidraw&utm_medium=app&utm_content=command_palette`,
        "_blank",
      );
    },
  };
  const ExcalidrawPlusAppCommand = {
    label: "Sign up",
    category: DEFAULT_CATEGORIES.links,
    predicate: true,
    icon: <div style={{ width: 14 }}>{ExcalLogo}</div>,
    keywords: [
      "excalidraw",
      "plus",
      "cloud",
      "server",
      "signin",
      "login",
      "signup",
    ],
    perform: () => {
      window.open(
        `${
          import.meta.env.VITE_APP_PLUS_APP
        }?utm_source=excalidraw&utm_medium=app&utm_content=command_palette`,
        "_blank",
      );
    },
  };

  return (
    <div
      ref={hintOverlayRootRef}
      style={{
        height: "100%",
        position: "relative",
      }}
      className={clsx("excalidraw-app", {
        "is-collaborating": isCollaborating,
      })}
    >
      <Excalidraw
        viewportStatusFrame={viewportStatusFrame}
        userToFollow={userToFollow}
        onChange={onChange}
        onExport={onExport}
        initialData={initialStatePromiseRef.current.promise}
        isCollaborating={isCollaborating}
        onPointerUpdate={collabAPI?.onPointerUpdate}
        UIOptions={{
          canvasActions: {
            toggleTheme: true,
            export: {
              onExportToBackend,
              renderCustomUI: excalidrawAPI
                ? (elements, appState, files) => {
                    return (
                      <ExportToExcalidrawPlus
                        elements={elements}
                        appState={appState}
                        files={files}
                        name={excalidrawAPI.getName()}
                        onError={(error) => {
                          excalidrawAPI?.updateScene({
                            appState: {
                              errorMessage: error.message,
                            },
                          });
                        }}
                        onSuccess={() => {
                          excalidrawAPI.updateScene({
                            appState: { openDialog: null },
                          });
                        }}
                      />
                    );
                  }
                : undefined,
            },
          },
        }}
        langCode={langCode}
        renderCustomStats={renderCustomStats}
        detectScroll={false}
        handleKeyboardGlobally={true}
        autoFocus={true}
        theme={editorTheme}
        onThemeChange={setAppTheme}
        renderTopRightUI={(isMobile) => {
          if (isMobile || !collabAPI || isCollabDisabled) {
            return null;
          }

          return (
            <div className="excalidraw-ui-top-right">
              {excalidrawAPI?.getEditorInterface().formFactor === "desktop" && (
                <ExcalidrawPlusPromoBanner
                  isSignedIn={isExcalidrawPlusSignedUser}
                />
              )}

              {collabError.message && <CollabError collabError={collabError} />}
              <LiveCollaborationTrigger
                isCollaborating={isCollaborating}
                onSelect={() =>
                  setShareDialogState({ isOpen: true, type: "share" })
                }
                editorInterface={editorInterface}
              />
            </div>
          );
        }}
        onLinkOpen={(element, event) => {
          if (element.link && isElementLink(element.link)) {
            event.preventDefault();
            excalidrawAPI?.setViewport({
              target: element.link,
              fit: "scale-down",
              animation: true,
            });
          }
        }}
      >
        <AppMainMenu
          onCollabDialogOpen={onCollabDialogOpen}
          isCollaborating={isCollaborating}
          isCollabEnabled={!isCollabDisabled}
          theme={appTheme}
          refresh={() => forceRefresh((prev) => !prev)}
        />
        <AppWelcomeScreen
          onCollabDialogOpen={onCollabDialogOpen}
          isCollabEnabled={!isCollabDisabled}
        />
        <OverwriteConfirmDialog>
          <OverwriteConfirmDialog.Actions.ExportToImage />
          <OverwriteConfirmDialog.Actions.SaveToDisk />
          {excalidrawAPI && (
            <OverwriteConfirmDialog.Action
              title={t("overwriteConfirm.action.excalidrawPlus.title")}
              actionLabel={t("overwriteConfirm.action.excalidrawPlus.button")}
              onClick={() => {
                exportToExcalidrawPlus(
                  excalidrawAPI.getSceneElements(),
                  excalidrawAPI.getAppState(),
                  excalidrawAPI.getFiles(),
                  excalidrawAPI.getName(),
                );
              }}
            >
              {t("overwriteConfirm.action.excalidrawPlus.description")}
            </OverwriteConfirmDialog.Action>
          )}
        </OverwriteConfirmDialog>
        <AppFooter onChange={() => excalidrawAPI?.refresh()} />
        {excalidrawAPI && <AIComponents excalidrawAPI={excalidrawAPI} />}

        <TTDDialogTrigger />
        {isCollaborating && isOffline && (
          <div className="alertalert--warning">
            {t("alerts.collabOfflineWarning")}
          </div>
        )}
        {localStorageQuotaExceeded && (
          <div className="alert alert--danger">
            {t("alerts.localStorageQuotaExceeded")}
          </div>
        )}
        {latestShareableLink && (
          <ShareableLinkDialog
            link={latestShareableLink}
            onCloseRequest={() => setLatestShareableLink(null)}
            setErrorMessage={setErrorMessage}
          />
        )}
        {excalidrawAPI && !isCollabDisabled && (
          <Collab excalidrawAPI={excalidrawAPI} />
        )}

        <ShareDialog
          collabAPI={collabAPI}
          onExportToBackend={async () => {
            if (excalidrawAPI) {
              try {
                await onExportToBackend(
                  excalidrawAPI.getSceneElements(),
                  excalidrawAPI.getAppState(),
                  excalidrawAPI.getFiles(),
                );
              } catch (error: any) {
                setErrorMessage(error.message);
              }
            }
          }}
        />

        <AppSidebar />

        {errorMessage && (
          <ErrorDialog onClose={() => setErrorMessage("")}>
            {errorMessage}
          </ErrorDialog>
        )}

        <CommandPalette
          customCommandPaletteItems={[
            {
              label: t("labels.liveCollaboration"),
              category: DEFAULT_CATEGORIES.app,
              keywords: [
                "team",
                "multiplayer",
                "share",
                "public",
                "session",
                "invite",
              ],
              icon: usersIcon,
              perform: () => {
                setShareDialogState({
                  isOpen: true,
                  type: "collaborationOnly",
                });
              },
            },
            {
              label: t("roomDialog.button_stopSession"),
              category: DEFAULT_CATEGORIES.app,
              predicate: () => !!collabAPI?.isCollaborating(),
              keywords: [
                "stop",
                "session",
                "end",
                "leave",
                "close",
                "exit",
                "collaboration",
              ],
              perform: () => {
                if (collabAPI) {
                  collabAPI.stopCollaboration();
                  if (!collabAPI.isCollaborating()) {
                    setShareDialogState({ isOpen: false });
                  }
                }
              },
            },
            {
              label: t("labels.share"),
              category: DEFAULT_CATEGORIES.app,
              predicate: true,
              icon: share,
              keywords: [
                "link",
                "shareable",
                "readonly",
                "export",
                "publish",
                "snapshot",
                "url",
                "collaborate",
                "invite",
              ],
              perform: async () => {
                setShareDialogState({ isOpen: true, type: "share" });
              },
            },
            {
              label: "GitHub",
              icon: GithubIcon,
              category: DEFAULT_CATEGORIES.links,
              predicate: true,
              keywords: [
                "issues",
                "bugs",
                "requests",
                "report",
                "features",
                "social",
                "community",
              ],
              perform: () => {
                window.open(
                  "https://github.com/excalidraw/excalidraw",
                  "_blank",
                  "noopener noreferrer",
                );
              },
            },
            {
              label: t("labels.followUs"),
              icon: XBrandIcon,
              category: DEFAULT_CATEGORIES.links,
              predicate: true,
              keywords: ["twitter", "contact", "social", "community"],
              perform: () => {
                window.open(
                  "https://x.com/excalidraw",
                  "_blank",
                  "noopener noreferrer",
                );
              },
            },
            {
              label: t("labels.discordChat"),
              category: DEFAULT_CATEGORIES.links,
              predicate: true,
              icon: DiscordIcon,
              keywords: [
                "chat",
                "talk",
                "contact",
                "bugs",
                "requests",
                "report",
                "feedback",
                "suggestions",
                "social",
                "community",
              ],
              perform: () => {
                window.open(
                  "https://discord.gg/UexuTaE",
                  "_blank",
                  "noopener noreferrer",
                );
              },
            },
            {
              label: "YouTube",
              icon: youtubeIcon,
              category: DEFAULT_CATEGORIES.links,
              predicate: true,
              keywords: ["features", "tutorials", "howto", "help", "community"],
              perform: () => {
                window.open(
                  "https://youtube.com/@excalidraw",
                  "_blank",
                  "noopener noreferrer",
                );
              },
            },
            ...(isExcalidrawPlusSignedUser
              ? [
                  {
                    ...ExcalidrawPlusAppCommand,
                    label: "Sign in / Go to Excalidraw+",
                  },
                ]
              : [ExcalidrawPlusCommand, ExcalidrawPlusAppCommand]),

            {
              label: t("overwriteConfirm.action.excalidrawPlus.button"),
              category: DEFAULT_CATEGORIES.export,
              icon: exportToPlus,
              predicate: true,
              keywords: ["plus", "export", "save", "backup"],
              perform: () => {
                if (excalidrawAPI) {
                  exportToExcalidrawPlus(
                    excalidrawAPI.getSceneElements(),
                    excalidrawAPI.getAppState(),
                    excalidrawAPI.getFiles(),
                    excalidrawAPI.getName(),
                  );
                }
              },
            },
            {
              label: t("labels.installPWA"),
              category: DEFAULT_CATEGORIES.app,
              predicate: () => !!pwaEvent,
              perform: () => {
                if (pwaEvent) {
                  pwaEvent.prompt();
                  pwaEvent.userChoice.then(() => {
                    // event cannot be reused, but we'll hopefully
                    // grab new one as the event should be fired again
                    pwaEvent = null;
                  });
                }
              },
            },
          ]}
        />
        {isVisualDebuggerEnabled() && excalidrawAPI && (
          <DebugCanvas
            appState={excalidrawAPI.getAppState()}
            scale={window.devicePixelRatio}
            ref={debugCanvasRef}
          />
        )}
      
      </Excalidraw>

      {/* =======================================================
          WHITEBOARD TUTOR HINT OVERLAY
          ======================================================= */}

      <div
        style={{
          position: "absolute",
          inset: 0,
          pointerEvents: "none",
          overflow: "hidden",
          zIndex: 20,
        }}
      >
        {whiteboardHints.map((hint) => {
          if (!hint.bbox) {
            return null;
          }

          const zoom = hintViewport.zoom;

          const wrapperRect =
            hintOverlayRootRef.current?.getBoundingClientRect();

          const wrapperLeft =
            wrapperRect?.left ?? 0;

          const wrapperTop =
            wrapperRect?.top ?? 0;

          // Convert scene coordinates -> screen coordinates
          const equationCenterX =
            (
              hint.bbox.x +
              hint.bbox.width / 2 +
              hintViewport.scrollX
            ) *
              zoom +
            hintViewport.offsetLeft -
            wrapperLeft;

          const equationTopY =
            (
              hint.bbox.y +
              hintViewport.scrollY
            ) *
              zoom +
            hintViewport.offsetTop -
            wrapperTop;

          return (
            <div
              key={hint.anchor_equation_id}
              style={{
                position: "absolute",

                left: equationCenterX,
                top: equationTopY - 12,

                transform:
                  "translate(-50%, -100%)",

                maxWidth: 280,
                minWidth: 160,

                padding: "10px 12px",

                borderRadius: 10,

                background:
                  "rgba(255,255,255,0.97)",

                border:
                  "1px solid rgba(0,0,0,0.14)",

                boxShadow:
                  "0 4px 16px rgba(0,0,0,0.16)",

                fontSize: 13,
                lineHeight: 1.4,

                textAlign: "left",

                pointerEvents: "none",
              }}
            >
              <strong>💡 Hint</strong>

              <div
                style={{
                  marginTop: 4,
                }}
              >
                {hint.instruction}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const ExcalidrawApp = () => {
  const isCloudExportWindow =
    window.location.pathname === "/excalidraw-plus-export";

  if (isCloudExportWindow) {
    return <ExcalidrawPlusIframeExport />;
  }

  return (
    <TopErrorBoundary>
      <Provider store={appJotaiStore}>
        <ExcalidrawAPIProvider>
          <ExcalidrawWrapper />
        </ExcalidrawAPIProvider>
      </Provider>
    </TopErrorBoundary>
  );
};
// const ExcalidrawApp = () => {
//   const isCloudExportWindow =
//     window.location.pathname === "/excalidraw-plus-export";

//   const [showPromptPage, setShowPromptPage] =
//     useState(true);

//   if (isCloudExportWindow) {
//     return <ExcalidrawPlusIframeExport />;
//   }

//   if (showPromptPage) {
//     return (
//       <PromptPage
//         onSubmit={(prompt) => {
//           console.log(
//             "[Excalidraw App] Received initial prompt:",
//             prompt,
//           );

//           setShowPromptPage(false);
//         }}
//       />
//     );
//   }

//   return (
//     <TopErrorBoundary>
//       <Provider store={appJotaiStore}>
//         <ExcalidrawAPIProvider>
//           <ExcalidrawWrapper />
//         </ExcalidrawAPIProvider>
//       </Provider>
//     </TopErrorBoundary>
//   );
// };
export default ExcalidrawApp;