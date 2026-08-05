"use client"

import * as React from "react"
import { Virtuoso, type VirtuosoHandle } from "react-virtuoso"

import { cn } from "../lib/utils"

export type TreeKey = string
export type TreeSelectionMode = "none" | "single" | "multiple"
export type TreeCheckRelation = "related" | "independent"
export type TreeDropPosition = "before" | "inside" | "after"
export type TreeScrollAlign = "start" | "center" | "end" | "auto"

export type TreeNodeData<T = unknown> = {
  key: TreeKey
  label: React.ReactNode
  icon?: React.ReactNode
  data?: T
  disabled?: boolean
  disableCheckbox?: boolean
  isLeaf?: boolean
  children?: readonly TreeNodeData<T>[]
}

export type TreeNodeState<T = unknown> = {
  node: TreeNodeData<T>
  depth: number
  index: number
  siblingCount: number
  expanded: boolean
  selected: boolean
  checked: boolean
  halfChecked: boolean
  disabled: boolean
  loading: boolean
  matched: boolean
  searchValue: string
}

export type TreeExpandedChange<T = unknown> = {
  expanded: boolean
  node: TreeNodeData<T>
}

export type TreeSelectionChange<T = unknown> = {
  selected: boolean
  node: TreeNodeData<T>
}

export type TreeCheckChange<T = unknown> = {
  checked: boolean
  node: TreeNodeData<T>
  halfCheckedKeys: TreeKey[]
}

export type TreeDropIntent<T = unknown> = {
  dragKey: TreeKey
  targetKey: TreeKey
  position: TreeDropPosition
  dragNode: TreeNodeData<T>
  targetNode: TreeNodeData<T>
}

export type TreeSearchConfig<T = unknown> = {
  value?: string
  defaultValue?: string
  placeholder?: string
  showMatchedOnly?: boolean
  filterNode?: (value: string, node: TreeNodeData<T>) => boolean
  onValueChange?: (value: string) => void
}

export type TreeLoadConfig<T = unknown> = {
  loadChildren: (node: TreeNodeData<T>) => Promise<readonly TreeNodeData<T>[] | void>
  loadedKeys?: readonly TreeKey[]
  defaultLoadedKeys?: readonly TreeKey[]
  onLoadedChange?: (loadedKeys: TreeKey[], node: TreeNodeData<T>) => void
  onLoadError?: (error: unknown, node: TreeNodeData<T>) => void
}

export type TreeDragConfig<T = unknown> = {
  canDrop?: (intent: TreeDropIntent<T>) => boolean
  onDrop?: (intent: TreeDropIntent<T>) => void
}

export type TreeVirtualizationConfig = {
  height: number | string
  overscan?: number
}

export type TreeRenderContext<T = unknown> = TreeNodeState<T> & {
  toggleExpanded: () => void
  toggleSelected: () => void
  toggleChecked: () => void
}

export type TreeHandle = {
  scrollToKey: (key: TreeKey, align?: TreeScrollAlign) => boolean
  focusKey: (key: TreeKey) => boolean
}

export type TreeProps<T = unknown> = Omit<React.ComponentProps<"div">, "children" | "draggable" | "onDrop" | "ref"> & {
  treeData: readonly TreeNodeData<T>[]
  disabled?: boolean
  expandedKeys?: readonly TreeKey[]
  defaultExpandedKeys?: readonly TreeKey[]
  onExpandedChange?: (keys: TreeKey[], detail: TreeExpandedChange<T>) => void
  selectionMode?: TreeSelectionMode
  selectedKeys?: readonly TreeKey[]
  defaultSelectedKeys?: readonly TreeKey[]
  onSelectedChange?: (keys: TreeKey[], detail: TreeSelectionChange<T>) => void
  checkable?: boolean
  checkedKeys?: readonly TreeKey[]
  defaultCheckedKeys?: readonly TreeKey[]
  checkRelation?: TreeCheckRelation
  leafOnly?: boolean
  onCheckedChange?: (keys: TreeKey[], detail: TreeCheckChange<T>) => void
  search?: TreeSearchConfig<T> | false
  load?: TreeLoadConfig<T>
  draggable?: boolean | TreeDragConfig<T>
  virtualization?: TreeVirtualizationConfig
  renderLabel?: (label: React.ReactNode, context: TreeRenderContext<T>) => React.ReactNode
  renderIcon?: (icon: React.ReactNode, context: TreeRenderContext<T>) => React.ReactNode
  renderNode?: (context: TreeRenderContext<T>, content: React.ReactNode) => React.ReactNode
  emptyContent?: React.ReactNode
  "aria-label"?: string
}

type IndexedNode<T> = {
  node: TreeNodeData<T>
  parentKey: TreeKey | null
  depth: number
  index: number
  siblingCount: number
  ancestors: readonly TreeKey[]
}

type TreeIndex<T> = {
  nodes: Map<TreeKey, IndexedNode<T>>
  roots: readonly TreeKey[]
}

type VisibleNode<T> = IndexedNode<T> & {
  expanded: boolean
  matched: boolean
}

type TreeValidation = { ok: true } | { ok: false; message: string }

const asKeys = (keys: readonly TreeKey[] | undefined): TreeKey[] => [...new Set(keys ?? [])]

const nodeChildren = <T,>(node: TreeNodeData<T>): readonly TreeNodeData<T>[] => node.children ?? []

const isBranch = <T,>(node: TreeNodeData<T>): boolean => node.isLeaf !== true && nodeChildren(node).length > 0

const validateTreeData = <T,>(treeData: readonly TreeNodeData<T>[]): TreeValidation => {
  const keys = new Set<TreeKey>()
  const active = new Set<object>()
  const visit = (nodes: readonly TreeNodeData<T>[]): TreeValidation => {
    for (const node of nodes) {
      if (!node || typeof node !== "object" || !node.key.trim()) return { ok: false, message: "Tree 节点 key 必须是非空字符串" }
      if (keys.has(node.key)) return { ok: false, message: `Tree 节点 key 重复: ${node.key}` }
      if (active.has(node)) return { ok: false, message: "Tree 不能包含循环引用" }
      keys.add(node.key)
      active.add(node)
      const children = nodeChildren(node)
      if (node.isLeaf === true && children.length) return { ok: false, message: `叶节点不能包含 children: ${node.key}` }
      const result = visit(children)
      active.delete(node)
      if (!result.ok) return result
    }
    return { ok: true }
  }
  return visit(treeData)
}

const buildTreeIndex = <T,>(treeData: readonly TreeNodeData<T>[]): TreeIndex<T> => {
  const nodes = new Map<TreeKey, IndexedNode<T>>()
  const visit = (items: readonly TreeNodeData<T>[], parentKey: TreeKey | null, depth: number, ancestors: readonly TreeKey[]) => {
    items.forEach((node, index) => {
      const nextAncestors = [...ancestors, node.key]
      nodes.set(node.key, { node, parentKey, depth, index, siblingCount: items.length, ancestors: nextAncestors })
      visit(nodeChildren(node), node.key, depth + 1, nextAncestors)
    })
  }
  visit(treeData, null, 1, [])
  return { nodes, roots: treeData.map((node) => node.key) }
}

const descendantKeys = <T,>(index: TreeIndex<T>, key: TreeKey): TreeKey[] => {
  const result: TreeKey[] = []
  const visit = (current: TreeKey) => {
    const node = index.nodes.get(current)?.node
    if (!node) return
    for (const child of nodeChildren(node)) {
      result.push(child.key)
      visit(child.key)
    }
  }
  visit(key)
  return result
}

const isDescendant = <T,>(index: TreeIndex<T>, key: TreeKey, possibleAncestor: TreeKey): boolean =>
  Boolean(index.nodes.get(key)?.ancestors.includes(possibleAncestor))

const flattenVisible = <T,>(
  index: TreeIndex<T>,
  expandedKeys: ReadonlySet<TreeKey>,
  matchedKeys: ReadonlySet<TreeKey>,
  showMatchedOnly: boolean,
): VisibleNode<T>[] => {
  const visible: VisibleNode<T>[] = []
  const shouldShow = (key: TreeKey) => !showMatchedOnly || matchedKeys.has(key) || expandedKeys.has(key)
  const visit = (keys: readonly TreeKey[]) => {
    for (const key of keys) {
      const item = index.nodes.get(key)
      if (!item || !shouldShow(key)) continue
      visible.push({ ...item, expanded: expandedKeys.has(key), matched: matchedKeys.has(key) })
      if (expandedKeys.has(key)) visit(nodeChildren(item.node).map((child) => child.key))
    }
  }
  visit(index.roots)
  return visible
}

const searchTree = <T,>(index: TreeIndex<T>, config: TreeSearchConfig<T> | false | undefined, value: string) => {
  const matchedKeys = new Set<TreeKey>()
  if (!value.trim()) return { matchedKeys, expandedKeys: new Set<TreeKey>() }
  for (const [key, item] of index.nodes) {
    const matched = config && config.filterNode ? config.filterNode(value, item.node) : String(item.node.label ?? "").toLocaleLowerCase().includes(value.toLocaleLowerCase())
    if (matched) matchedKeys.add(key)
  }
  const expandedKeys = new Set<TreeKey>()
  for (const key of matchedKeys) {
    const ancestors = index.nodes.get(key)?.ancestors ?? []
    ancestors.slice(0, -1).forEach((ancestor) => expandedKeys.add(ancestor))
  }
  return { matchedKeys, expandedKeys }
}

const getCheckableChildren = <T,>(index: TreeIndex<T>, key: TreeKey): TreeKey[] =>
  nodeChildren(index.nodes.get(key)?.node ?? ({} as TreeNodeData<T>)).filter((node) => !node.disabled && !node.disableCheckbox).map((node) => node.key)

const calculateRelatedState = <T,>(index: TreeIndex<T>, checkedKeys: ReadonlySet<TreeKey>) => {
  const checked = new Set(checkedKeys)
  const halfChecked = new Set<TreeKey>()
  const visit = (key: TreeKey) => {
    const children = getCheckableChildren(index, key)
    children.forEach(visit)
    if (!children.length) return
    const checkedCount = children.filter((child) => checked.has(child)).length
    const halfCount = children.filter((child) => halfChecked.has(child)).length
    if (checkedCount === children.length) {
      checked.add(key)
      halfChecked.delete(key)
    } else if (checkedCount || halfCount) {
      checked.delete(key)
      halfChecked.add(key)
    } else {
      checked.delete(key)
      halfChecked.delete(key)
    }
  }
  index.roots.forEach(visit)
  return { checked, halfChecked }
}

const toggleChecked = <T,>(index: TreeIndex<T>, current: ReadonlySet<TreeKey>, key: TreeKey, relation: TreeCheckRelation) => {
  if (relation === "independent") {
    const checked = new Set(current)
    if (checked.has(key)) checked.delete(key)
    else checked.add(key)
    return { checked, halfChecked: new Set<TreeKey>() }
  }
  const normalized = calculateRelatedState(index, current)
  const shouldCheck = !normalized.checked.has(key) || normalized.halfChecked.has(key)
  const checked = new Set(normalized.checked)
  const targets = [key, ...descendantKeys(index, key)].filter((target) => {
    const node = index.nodes.get(target)?.node
    return Boolean(node && !node.disabled && !node.disableCheckbox)
  })
  targets.forEach((target) => shouldCheck ? checked.add(target) : checked.delete(target))
  return calculateRelatedState(index, checked)
}

const useControllableKeys = (
  value: readonly TreeKey[] | undefined,
  defaultValue: readonly TreeKey[] | undefined,
  onChange: ((keys: TreeKey[]) => void) | undefined,
) => {
  const [internal, setInternal] = React.useState(() => asKeys(defaultValue))
  const controlled = value !== undefined
  const current = controlled ? asKeys(value) : internal
  const update = (next: TreeKey[]) => {
    if (!controlled) setInternal(next)
    onChange?.(next)
  }
  return [new Set(current), update] as const
}

const getDropIntent = <T,>(
  index: TreeIndex<T>,
  dragKey: TreeKey,
  targetKey: TreeKey,
  position: TreeDropPosition,
): TreeDropIntent<T> | null => {
  if (dragKey === targetKey || (position === "inside" && isDescendant(index, targetKey, dragKey))) return null
  const dragNode = index.nodes.get(dragKey)?.node
  const targetNode = index.nodes.get(targetKey)?.node
  return dragNode && targetNode ? { dragKey, targetKey, position, dragNode, targetNode } : null
}

const TreeRow = <T,>({
  context,
  renderLabel,
  renderIcon,
  renderNode,
  onExpand,
  onSelect,
  onCheck,
  onKeyDown,
  onFocus,
  tabIndex,
  checkable,
  draggable,
  onDragStart,
  onDragOver,
  onDrop,
}: {
  context: TreeRenderContext<T>
  renderLabel?: TreeProps<T>["renderLabel"]
  renderIcon?: TreeProps<T>["renderIcon"]
  renderNode?: TreeProps<T>["renderNode"]
  onExpand: () => void
  onSelect: () => void
  onCheck: () => void
  onKeyDown: (event: React.KeyboardEvent<HTMLDivElement>) => void
  onFocus: () => void
  tabIndex: number
  checkable: boolean
  draggable: boolean
  onDragStart: (event: React.DragEvent<HTMLDivElement>) => void
  onDragOver: (event: React.DragEvent<HTMLDivElement>) => void
  onDrop: (event: React.DragEvent<HTMLDivElement>) => void
}) => {
  const { node } = context
  const hasChildren = isBranch(node) || node.isLeaf === false
  const label = renderLabel ? renderLabel(node.label, context) : node.label
  const icon = renderIcon ? renderIcon(node.icon, context) : node.icon
  const content = (
    <div className="flex min-w-0 flex-1 items-center gap-1.5">
      {hasChildren ? (
        <button type="button" tabIndex={-1} aria-label={context.expanded ? "收起" : "展开"} className="inline-flex size-5 shrink-0 items-center justify-center rounded hover:bg-accent" onClick={(event) => { event.stopPropagation(); onExpand() }}>
          <span aria-hidden="true" className={cn("transition-transform", context.expanded && "rotate-90")}>›</span>
        </button>
      ) : <span className="inline-block size-5 shrink-0" />}
      {checkable && context.node.disableCheckbox !== true ? (
        <input type="checkbox" tabIndex={-1} checked={context.checked} disabled={context.disabled} aria-label={`选择 ${String(node.label)}`} onChange={onCheck} onClick={(event) => event.stopPropagation()} ref={(element) => { if (element) element.indeterminate = context.halfChecked }} />
      ) : null}
      {icon ? <span className="shrink-0" aria-hidden="true">{icon}</span> : null}
      <span className="min-w-0 truncate">{label}</span>
      {context.loading ? <span className="ml-auto text-xs text-muted-foreground" aria-label="加载中">…</span> : null}
    </div>
  )
  const rendered = renderNode ? renderNode(context, content) : content
  return (
    <div
      role="treeitem"
      aria-level={context.depth}
      aria-posinset={context.index + 1}
      aria-setsize={context.siblingCount}
      aria-expanded={hasChildren ? context.expanded : undefined}
      aria-selected={context.selected}
      aria-checked={checkable ? context.checked ? true : context.halfChecked ? "mixed" : false : undefined}
      aria-disabled={context.disabled}
      tabIndex={tabIndex}
      draggable={draggable && !context.disabled}
      className={cn("flex min-h-8 w-full items-center rounded-md px-1.5 text-sm outline-none hover:bg-accent/60 focus-visible:ring-2 focus-visible:ring-ring", context.selected && "bg-accent", context.disabled && "cursor-not-allowed opacity-50")}
      onClick={onSelect}
      onFocus={onFocus}
      onKeyDown={onKeyDown}
      onDragStart={onDragStart}
      onDragOver={onDragOver}
      onDrop={onDrop}
    >
      <span className="mr-1" style={{ width: Math.max(0, context.depth - 1) * 16 }} aria-hidden="true" />
      {rendered}
    </div>
  )
}

const TreeImpl = <T,>(props: TreeProps<T>, ref: React.ForwardedRef<TreeHandle>) => {
  const {
    treeData, disabled = false, className, expandedKeys, defaultExpandedKeys, onExpandedChange,
    selectionMode = "single", selectedKeys, defaultSelectedKeys, onSelectedChange,
    checkable = false, checkedKeys, defaultCheckedKeys, checkRelation = "related", leafOnly = false, onCheckedChange,
    search = false, load, draggable = false, virtualization, renderLabel, renderIcon, renderNode, emptyContent,
    "aria-label": ariaLabel = "Tree",
    ...divProps
  } = props
  const validation = React.useMemo(() => validateTreeData(treeData), [treeData])
  const index = React.useMemo(() => validation.ok ? buildTreeIndex(treeData) : null, [treeData, validation.ok])
  const [expanded, setExpanded] = useControllableKeys(expandedKeys, defaultExpandedKeys, undefined)
  const [selected, setSelected] = useControllableKeys(selectedKeys, defaultSelectedKeys, undefined)
  const [checked, setChecked] = useControllableKeys(checkedKeys, defaultCheckedKeys, undefined)
  const [loaded, setLoaded] = useControllableKeys(load?.loadedKeys, load?.defaultLoadedKeys, undefined)
  const [searchInternal, setSearchInternal] = React.useState(search ? search.defaultValue ?? "" : "")
  const searchValue = search && search.value !== undefined ? search.value : searchInternal
  const [loadingKeys, setLoadingKeys] = React.useState<ReadonlySet<TreeKey>>(new Set())
  const [focusedKey, setFocusedKey] = React.useState<TreeKey | null>(null)
  const [dragKey, setDragKey] = React.useState<TreeKey | null>(null)
  const [dropIntent, setDropIntent] = React.useState<TreeDropIntent<T> | null>(null)
  const pendingLoads = React.useRef(new Map<TreeKey, Promise<unknown>>())
  const listRef = React.useRef<VirtuosoHandle>(null)
  const rowRefs = React.useRef(new Map<TreeKey, HTMLDivElement>())

  const searchResult = React.useMemo(() => index ? searchTree(index, search, searchValue) : { matchedKeys: new Set<TreeKey>(), expandedKeys: new Set<TreeKey>() }, [index, search, searchValue])
  const effectiveExpanded = React.useMemo(() => new Set([...expanded, ...searchResult.expandedKeys]), [expanded, searchResult.expandedKeys])
  const visibleNodes = React.useMemo(() => index ? flattenVisible(index, effectiveExpanded, searchResult.matchedKeys, Boolean(search && search.showMatchedOnly)) : [], [index, effectiveExpanded, search, searchResult.matchedKeys])
  const derivedCheck = React.useMemo(() => index && checkRelation === "related" ? calculateRelatedState(index, checked) : { checked, halfChecked: new Set<TreeKey>() }, [index, checked, checkRelation])
  const visibleKeys = React.useMemo(() => visibleNodes.map((item) => item.node.key), [visibleNodes])
  const hasSearch = Boolean(search)

  React.useEffect(() => {
    if (!focusedKey || !visibleKeys.includes(focusedKey)) setFocusedKey(visibleKeys[0] ?? null)
  }, [focusedKey, visibleKeys])

  const focusRow = (key: TreeKey) => rowRefs.current.get(key)?.querySelector<HTMLElement>('[role="treeitem"]')?.focus()

  const emitExpanded = (key: TreeKey) => {
    if (!index) return
    const node = index.nodes.get(key)?.node
    if (!node) return
    const next = new Set(expanded)
    const nextValue = next.has(key) ? (next.delete(key), false) : (next.add(key), true)
    setExpanded([...next])
    onExpandedChange?.([...next], { expanded: nextValue, node })
  }

  const emitSelected = (key: TreeKey) => {
    if (!index || disabled) return
    const node = index.nodes.get(key)?.node
    if (!node || node.disabled) return
    const next = new Set(selected)
    const isSelected = next.has(key)
    if (selectionMode === "none") return
    if (selectionMode === "single") {
      next.clear()
      next.add(key)
    } else if (isSelected) next.delete(key)
    else next.add(key)
    setSelected([...next])
    onSelectedChange?.([...next], { selected: !isSelected, node })
  }

  const emitChecked = (key: TreeKey) => {
    if (!index || !checkable || disabled) return
    const node = index.nodes.get(key)?.node
    if (!node || node.disabled || node.disableCheckbox) return
    const next = toggleChecked(index, checked, key, checkRelation)
    const output = leafOnly ? [...next.checked].filter((item) => !isBranch(index.nodes.get(item)?.node ?? ({} as TreeNodeData<T>))) : [...next.checked]
    setChecked([...next.checked])
    onCheckedChange?.(output, { checked: next.checked.has(key), node, halfCheckedKeys: [...next.halfChecked] })
  }

  const loadNode = async (node: TreeNodeData<T>) => {
    if (!load || node.isLeaf || nodeChildren(node).length || loaded.has(node.key) || pendingLoads.current.has(node.key)) return
    const promise = load.loadChildren(node)
    pendingLoads.current.set(node.key, promise)
    setLoadingKeys((current) => new Set(current).add(node.key))
    try {
      await promise
      const next = new Set(loaded).add(node.key)
      setLoaded([...next])
      load.onLoadedChange?.([...next], node)
    } catch (error) {
      load.onLoadError?.(error, node)
    } finally {
      pendingLoads.current.delete(node.key)
      setLoadingKeys((current) => { const next = new Set(current); next.delete(node.key); return next })
    }
  }

  const handleExpand = (key: TreeKey) => {
    const node = index?.nodes.get(key)?.node
    if (node) void loadNode(node)
    emitExpanded(key)
  }

  const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>, key: TreeKey) => {
    if (!index) return
    const currentIndex = visibleKeys.indexOf(key)
    if (currentIndex < 0) return
    const focusAt = (nextKey: TreeKey | undefined) => {
      if (!nextKey) return
      event.preventDefault()
      setFocusedKey(nextKey)
      focusRow(nextKey)
    }
    if (event.key === "Enter") { event.preventDefault(); emitSelected(key); return }
    if (event.key === " " && checkable) { event.preventDefault(); emitChecked(key); return }
    if (event.key === "ArrowDown") { focusAt(visibleKeys[currentIndex + 1]); return }
    if (event.key === "ArrowUp") { focusAt(visibleKeys[currentIndex - 1]); return }
    if (event.key === "Home") { focusAt(visibleKeys[0]); return }
    if (event.key === "End") { focusAt(visibleKeys[visibleKeys.length - 1]); return }
    const item = index.nodes.get(key)
    if (!item) return
    if (event.key === "ArrowRight") {
      if (!effectiveExpanded.has(key) && (isBranch(item.node) || item.node.isLeaf === false)) { event.preventDefault(); handleExpand(key); return }
      const next = visibleNodes[currentIndex + 1]
      if (next && next.depth > item.depth) focusAt(next.node.key)
      return
    }
    if (event.key === "ArrowLeft") {
      if (effectiveExpanded.has(key)) { event.preventDefault(); handleExpand(key); return }
      focusAt(item.parentKey ?? undefined)
    }
  }

  const getRowContext = (item: VisibleNode<T>): TreeRenderContext<T> => ({
    node: item.node, depth: item.depth, index: item.index, siblingCount: item.siblingCount,
    expanded: item.expanded, selected: selected.has(item.node.key), checked: derivedCheck.checked.has(item.node.key), halfChecked: derivedCheck.halfChecked.has(item.node.key),
    disabled: disabled || Boolean(item.node.disabled), loading: loadingKeys.has(item.node.key), matched: item.matched, searchValue,
    toggleExpanded: () => handleExpand(item.node.key), toggleSelected: () => emitSelected(item.node.key), toggleChecked: () => emitChecked(item.node.key),
  })

  const getIntent = (event: React.DragEvent<HTMLDivElement>, targetKey: TreeKey): TreeDropIntent<T> | null => {
    if (!index || !dragKey) return null
    const rect = event.currentTarget.getBoundingClientRect()
    const ratio = rect.height ? (event.clientY - rect.top) / rect.height : 0.5
    const position: TreeDropPosition = ratio < 0.25 ? "before" : ratio > 0.75 ? "after" : "inside"
    return getDropIntent(index, dragKey, targetKey, position)
  }

  React.useImperativeHandle(ref, () => ({
    scrollToKey: (key, align = "auto") => {
      const indexOf = visibleKeys.indexOf(key)
      if (indexOf < 0) return false
      if (virtualization) listRef.current?.scrollToIndex({ index: indexOf, align: align === "auto" ? undefined : align })
      else rowRefs.current.get(key)?.scrollIntoView({ block: align === "auto" ? "nearest" : align, behavior: "smooth" })
      return true
    },
    focusKey: (key) => {
      if (!visibleKeys.includes(key)) return false
      setFocusedKey(key)
      focusRow(key)
      return true
    },
  }), [visibleKeys, virtualization])

  if (!validation.ok || !index) return null

  const renderRow = (item: VisibleNode<T>) => {
    const context = getRowContext(item)
    const onDragStart = (event: React.DragEvent<HTMLDivElement>) => { setDragKey(item.node.key); event.dataTransfer.effectAllowed = "move" }
    const onDragOver = (event: React.DragEvent<HTMLDivElement>) => {
      if (!draggable) return
      const intent = getIntent(event, item.node.key)
      if (!intent) { setDropIntent(null); return }
      if (typeof draggable !== "boolean" && draggable.canDrop && !draggable.canDrop(intent)) { setDropIntent(null); return }
      event.preventDefault(); setDropIntent(intent)
    }
    const onDrop = (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault()
      const intent = dropIntent ?? getIntent(event, item.node.key)
      if (intent && typeof draggable !== "boolean") draggable.onDrop?.(intent)
      setDragKey(null); setDropIntent(null)
    }
    return (
      <div key={item.node.key} ref={(element) => { if (element) rowRefs.current.set(item.node.key, element); else rowRefs.current.delete(item.node.key) }}>
        <TreeRow context={context} renderLabel={renderLabel} renderIcon={renderIcon} renderNode={renderNode} onExpand={() => handleExpand(item.node.key)} onSelect={() => emitSelected(item.node.key)} onCheck={() => emitChecked(item.node.key)} onKeyDown={(event) => handleKeyDown(event, item.node.key)} onFocus={() => setFocusedKey(item.node.key)} tabIndex={focusedKey === item.node.key ? 0 : -1} checkable={checkable} draggable={Boolean(draggable)} onDragStart={onDragStart} onDragOver={onDragOver} onDrop={onDrop} />
      </div>
    )
  }

  return (
    <div className={cn("flex min-w-0 flex-col gap-1", className)} {...divProps}>
      {hasSearch ? <input role="searchbox" aria-label="搜索 Tree" placeholder={search ? search.placeholder : undefined} value={searchValue} onChange={(event) => { const value = event.target.value; if (search && search.value === undefined) setSearchInternal(value); if (search) search.onValueChange?.(value) }} className="mb-1 h-8 rounded-md border border-input bg-background px-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" /> : null}
      <div role="tree" aria-label={ariaLabel} aria-disabled={disabled}>
        {visibleNodes.length ? virtualization ? <Virtuoso ref={listRef} data={visibleNodes} style={{ height: virtualization.height }} increaseViewportBy={virtualization.overscan} itemContent={(_index, item) => renderRow(item)} /> : visibleNodes.map(renderRow) : emptyContent ?? <div className="px-2 py-4 text-sm text-muted-foreground">暂无数据</div>}
      </div>
    </div>
  )
}

export const Tree = React.forwardRef(TreeImpl) as <T = unknown>(props: TreeProps<T> & React.RefAttributes<TreeHandle>) => React.ReactElement | null
