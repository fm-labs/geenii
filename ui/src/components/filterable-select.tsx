import { useState, useRef, useEffect } from "react";
import { Check, ChevronsUpDown, Search, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

/**
 * FilterableSelect
 *
 * Props:
 *  - options:      Array<{ value: string; label: string }> — the full list of options
 *  - value:        string | null — currently selected value (controlled)
 *  - onChange:     (value: string | null) => void
 *  - placeholder:  string  — trigger button placeholder text
 *  - searchPlaceholder: string — search input placeholder
 *  - disabled:     boolean
 *  - className:    string — extra classes for the trigger button
 */
export function FilterableSelect({
                                   options = [],
                                   value = null,
                                   onChange,
                                   placeholder = "Select an option…",
                                   searchPlaceholder = "Search…",
                                   disabled = false,
                                   className,
                                 }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const inputRef = useRef(null);

  // Focus the search input whenever the popover opens
  useEffect(() => {
    if (open) {
      // Small delay so the popover has time to render
      setTimeout(() => inputRef.current?.focus(), 50);
    } else {
      setQuery("");
    }
  }, [open]);

  const filtered = options.filter((opt) =>
    opt.label.toLowerCase().includes(query.toLowerCase())
  );

  const selectedLabel = options.find((o) => o.value === value)?.label;

  function handleSelect(optValue) {
    onChange?.(optValue === value ? null : optValue);
    setOpen(false);
  }

  function clearSelection(e) {
    e.stopPropagation();
    onChange?.(null);
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          disabled={disabled}
          className={cn(
            "w-full justify-between font-normal",
            !selectedLabel && "text-muted-foreground",
            className
          )}
        >
          <span className="truncate">
            {selectedLabel ?? placeholder}
          </span>

          <span className="ml-2 flex shrink-0 items-center gap-1">
            {value && (
              <span
                role="button"
                tabIndex={0}
                onClick={clearSelection}
                onKeyDown={(e) => e.key === "Enter" && clearSelection(e)}
                className="rounded-sm p-0.5 opacity-60 hover:opacity-100 hover:bg-accent transition-colors"
                aria-label="Clear selection"
              >
                <X className="h-3.5 w-3.5" />
              </span>
            )}
            <ChevronsUpDown className="h-4 w-4 opacity-50" />
          </span>
        </Button>
      </PopoverTrigger>

      <PopoverContent
        className="w-[var(--radix-popover-trigger-width)] p-0"
        align="start"
      >
        {/* Search bar */}
        <div className="flex items-center border-b px-3">
          <Search className="mr-2 h-4 w-4 shrink-0 text-muted-foreground" />
          <Input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={searchPlaceholder}
            className="h-10 border-0 p-0 shadow-none focus-visible:ring-0 text-sm"
          />
          {query && (
            <button
              onClick={() => setQuery("")}
              className="ml-1 rounded-sm opacity-60 hover:opacity-100"
              aria-label="Clear search"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        {/* Options list */}
        <ul
          role="listbox"
          className="max-h-60 overflow-y-auto py-1 text-sm"
          aria-label="Options"
        >
          {filtered.length === 0 ? (
            <li className="py-6 text-center text-sm text-muted-foreground">
              No results found.
            </li>
          ) : (
            filtered.map((opt) => {
              const isSelected = value === opt.value;
              return (
                <li
                  key={opt.value}
                  role="option"
                  aria-selected={isSelected}
                  onClick={() => handleSelect(opt.value)}
                  className={cn(
                    "relative flex cursor-pointer select-none items-center rounded-sm mx-1 px-3 py-2 outline-none",
                    "hover:bg-accent hover:text-accent-foreground transition-colors",
                    isSelected && "bg-accent/50 font-medium"
                  )}
                >
                  <Check
                    className={cn(
                      "mr-2 h-4 w-4 shrink-0 transition-opacity",
                      isSelected ? "opacity-100 text-primary" : "opacity-0"
                    )}
                  />
                  {opt.label}
                </li>
              );
            })
          )}
        </ul>

        {/* Footer: result count */}
        <div className="border-t px-3 py-2 flex justify-between items-center">
          <span className="text-xs text-muted-foreground">
            {filtered.length} of {options.length} options
          </span>
          {value && (
            <Badge variant="secondary" className="text-xs">
              {selectedLabel}
            </Badge>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}

// ---------------------------------------------------------------------------
// Demo / usage example — remove or replace with your own page
// ---------------------------------------------------------------------------
const DEMO_OPTIONS = [
  { value: "react",       label: "React" },
  { value: "vue",        label: "Vue" },
  { value: "svelte",     label: "Svelte" },
  { value: "angular",    label: "Angular" },
  { value: "solid",      label: "SolidJS" },
  { value: "qwik",       label: "Qwik" },
  { value: "astro",      label: "Astro" },
  { value: "remix",      label: "Remix" },
  { value: "next",       label: "Next.js" },
  { value: "nuxt",       label: "Nuxt" },
  { value: "sveltekit",  label: "SvelteKit" },
  { value: "gatsby",     label: "Gatsby" },
];

// export default function App() {
//   const [selected, setSelected] = useState(null);
//
//   return (
//     <div className="min-h-screen bg-background flex items-center justify-center p-8">
//       <div className="w-full max-w-sm space-y-4">
//         <div>
//           <h1 className="text-lg font-semibold">Filterable Select</h1>
//           <p className="text-sm text-muted-foreground">
//             Pick a framework from the list.
//           </p>
//         </div>
//
//         <FilterableSelect
//           options={DEMO_OPTIONS}
//           value={selected}
//           onChange={setSelected}
//           placeholder="Choose a framework…"
//           searchPlaceholder="Filter frameworks…"
//         />
//
//         {selected && (
//           <p className="text-sm text-muted-foreground">
//             Selected: <span className="font-medium text-foreground">{selected}</span>
//           </p>
//         )}
//       </div>
//     </div>
//   );
// }