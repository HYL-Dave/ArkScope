import React, {
  useId,
  useRef,
  type KeyboardEvent,
  type ReactNode,
  type Ref,
} from "react";

export interface TabItem<Value extends string> {
  value: Value;
  label: ReactNode;
  panel: ReactNode;
  tabRef?: Ref<HTMLButtonElement>;
}

export interface TabsProps<Value extends string> {
  ariaLabel: string;
  value: Value;
  items: readonly TabItem<Value>[];
  onValueChange: (value: Value) => boolean | void;
  className?: string;
}

function assignRef<T>(ref: Ref<T> | undefined, value: T | null) {
  if (typeof ref === "function") {
    ref(value);
  } else if (ref) {
    (ref as { current: T | null }).current = value;
  }
}

export function Tabs<Value extends string>({
  ariaLabel,
  value,
  items,
  onValueChange,
  className = "",
}: TabsProps<Value>) {
  const namespace = `ui-tabs-${useId().replaceAll(":", "")}`;
  const tabRefs = useRef(new Map<Value, HTMLButtonElement>());
  const selectedIndex = items.findIndex((item) => item.value === value);
  const selectedItem = selectedIndex >= 0 ? items[selectedIndex] : null;

  function requestValue(nextValue: Value) {
    const accepted = onValueChange(nextValue) !== false;
    const focusValue = accepted ? nextValue : value;
    tabRefs.current.get(focusValue)?.focus();
  }

  function onTabKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let nextIndex: number | null = null;
    if (event.key === "ArrowRight") nextIndex = (index + 1) % items.length;
    if (event.key === "ArrowLeft") nextIndex = (index - 1 + items.length) % items.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = items.length - 1;
    if (nextIndex == null || items.length === 0) return;
    event.preventDefault();
    requestValue(items[nextIndex].value);
  }

  return (
    <div className={`ui-tabs ${className}`.trim()}>
      <div className="ui-tab-list" role="tablist" aria-label={ariaLabel}>
        {items.map((item, index) => {
          const selected = item.value === value;
          const tabId = `${namespace}-tab-${index}`;
          const panelId = `${namespace}-panel-${index}`;
          return (
            <button
              key={item.value}
              ref={(node) => {
                if (node) tabRefs.current.set(item.value, node);
                else tabRefs.current.delete(item.value);
                assignRef(item.tabRef, node);
              }}
              id={tabId}
              className="ui-tab"
              type="button"
              role="tab"
              tabIndex={selected ? 0 : -1}
              aria-selected={selected}
              aria-controls={panelId}
              onClick={() => requestValue(item.value)}
              onKeyDown={(event) => onTabKeyDown(event, index)}
            >
              {item.label}
            </button>
          );
        })}
      </div>
      {selectedItem ? (
        <div
          id={`${namespace}-panel-${selectedIndex}`}
          className="ui-tab-panel"
          role="tabpanel"
          aria-labelledby={`${namespace}-tab-${selectedIndex}`}
        >
          {selectedItem.panel}
        </div>
      ) : null}
    </div>
  );
}
