declare module "pdfjs-dist/build/pdf.mjs" {
  export const GlobalWorkerOptions: {
    workerSrc: string;
  };

  export function getDocument(options: { url: string; cMapPacked?: boolean }): {
    promise: Promise<unknown>;
    destroy?: () => Promise<void> | void;
  };
}
