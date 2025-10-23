declare module 'number-flip' {
  export interface FlipOptions {
    node: HTMLElement;
    from?: number;
    to?: number;
    duration?: number;
    delay?: number;
    easeFn?: (pos: number) => number;
    systemArr?: string[] | number[];
    direct?: boolean;
    separator?: string | string[];
    separateEvery?: number;
    containerClassName?: string;
    digitClassName?: string;
    separatorClassName?: string;
  }

  export interface FlipToOptions {
    to: number;
    duration?: number;
    easeFn?: (pos: number) => number;
    direct?: boolean;
  }

  export class Flip {
    constructor(options: FlipOptions);
    flipTo(options: FlipToOptions): void;
  }
}
