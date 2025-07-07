declare module '@sentool/fetch-event-source' {
  export interface EventSourceMessage {
    id: string;
    event: string;
    data: string;
    retry?: number;
  }

  export type EventSourceListener = (event: EventSourceMessage) => void;

  export interface FetchEventSourceInit extends RequestInit {
    onopen?: (response: Response) => Promise<void>;
    onmessage?: EventSourceListener;
    onclose?: () => void;
    onerror?: (err: any) => number | null | undefined | void;
    signal?: AbortSignal;
  }

  export function fetchEventSource(
    input: RequestInfo,
    init: FetchEventSourceInit
  ): Promise<void>;
} 