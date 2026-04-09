export interface RawDoc {
    doc_id:            string;
    title:             string;
    version:           string;
    issue_date:        string;
    supersedes:        string[];
    added_sections:    number;
    removed_sections:  number;
    changed_sections:  number;
}

export interface TEvent {
    doc_id:     string;
    base:       string;
    ver:        string;        // "" | "A" | "B" | …
    title:      string;
    issue_date: string;
    supersedes: string[];
    added:      number;
    removed:    number;
    changed:    number;
    total:      number;
    xi:         number;        // column index → X position
    yi:         number;        // row index    → Y position
    step:       number;        // playback order (0-based)
}

// Layout constants
export const ML = 164;   // left margin (Y-axis labels)
export const MT = 72;    // top margin  (X-axis labels)
export const CW = 108;   // column width
export const RH = 68;    // row height
export const MR = 48;    // right margin
export const MB = 48;    // bottom margin
