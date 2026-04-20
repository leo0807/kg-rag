declare module "mammoth" {
    interface ConvertResult {
        value: string;
        messages: unknown[];
    }
    interface Options {
        arrayBuffer?: ArrayBuffer;
        path?: string;
    }
    export function convertToHtml(input: Options): Promise<ConvertResult>;
}
