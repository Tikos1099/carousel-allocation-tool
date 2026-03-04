"use client"

import { useEffect, useMemo } from "react"
import { ArrowLeft, ArrowRight } from "lucide-react"

import type { WizardState } from "@/app/wizard/page"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

const RULE_LABELS = {
  multi: "Regle 1 - Multi-carousels",
  narrow_wide: "Regle 2 - Narrow vers Wide",
  extras: "Regle 3 - Extras",
} as const

type RuleId = keyof typeof RULE_LABELS

const RULE_ORDER: RuleId[] = ["multi", "narrow_wide", "extras"]

interface StepExtrasProps {
  state: WizardState
  updateState: (updates: Partial<WizardState>) => void
  onNext: () => void
  onPrevious: () => void
}

function normalizeRuleOrder(order: RuleId[], enabled: RuleId[]) {
  if (enabled.length === 0) return []
  const normalized = order.filter((rule) => enabled.includes(rule))
  RULE_ORDER.forEach((rule) => {
    if (enabled.includes(rule) && !normalized.includes(rule)) {
      normalized.push(rule)
    }
  })
  return normalized
}

function arraysEqual(a: RuleId[], b: RuleId[]) {
  if (a.length !== b.length) return false
  return a.every((value, index) => value === b[index])
}

export function StepExtras({ state, updateState, onNext, onPrevious }: StepExtrasProps) {
  const enabledRules = useMemo<RuleId[]>(() => {
    if (!state.rules.applyReadjustment) return []
    const rules: RuleId[] = []
    if (state.rules.ruleMulti) rules.push("multi")
    if (state.rules.ruleNarrowWide) rules.push("narrow_wide")
    if (state.rules.ruleExtras) rules.push("extras")
    return rules
  }, [
    state.rules.applyReadjustment,
    state.rules.ruleMulti,
    state.rules.ruleNarrowWide,
    state.rules.ruleExtras,
  ])

  const normalizedRuleOrder = useMemo(
    () => normalizeRuleOrder(state.rules.ruleOrder, enabledRules),
    [state.rules.ruleOrder, enabledRules]
  )

  useEffect(() => {
    if (!arraysEqual(state.rules.ruleOrder, normalizedRuleOrder)) {
      updateState({
        rules: {
          ...state.rules,
          ruleOrder: normalizedRuleOrder,
        },
      })
    }
  }, [normalizedRuleOrder, state.rules, updateState])

  const terminals = useMemo(() => {
    const fromCarousels = Array.from(
      new Set(
        state.carousels
          .map((carousel) => String(carousel.terminal || "").trim())
          .filter((term) => term)
      )
    )

    if (fromCarousels.length > 0) {
      return fromCarousels.sort()
    }

    const fromMapping = Array.from(
      new Set(
        Object.values(state.terminalMapping || {})
          .map((term) => String(term || "").trim())
          .filter((term) => term && term.toLowerCase() !== "ignore")
      )
    )

    if (fromMapping.length > 0) {
      return fromMapping.sort()
    }

    return ["ALL"]
  }, [state.carousels, state.terminalMapping])

  const defaultCapsByTerminal = useMemo(() => {
    const capsByTerminal: Record<string, { wide: number; narrow: number }> = {}
    let globalWide = 0
    let globalNarrow = 0

    state.carousels.forEach((carousel) => {
      const term = String(carousel.terminal || "").trim()
      if (!term) return
      const wide = Number(carousel.wideCapacity || 0)
      const narrow = Number(carousel.narrowCapacity || 0)
      globalWide = Math.max(globalWide, wide)
      globalNarrow = Math.max(globalNarrow, narrow)
      if (!capsByTerminal[term]) {
        capsByTerminal[term] = { wide, narrow }
      } else {
        capsByTerminal[term] = {
          wide: Math.max(capsByTerminal[term].wide, wide),
          narrow: Math.max(capsByTerminal[term].narrow, narrow),
        }
      }
    })

    const fallback = {
      wide: globalWide > 0 ? globalWide : 8,
      narrow: globalNarrow > 0 ? globalNarrow : 4,
    }

    const defaults: Record<string, { wide: number; narrow: number }> = {}
    terminals.forEach((term) => {
      defaults[term] = capsByTerminal[term] || fallback
    })
    return defaults
  }, [state.carousels, terminals])

  useEffect(() => {
    if (terminals.length === 0) return
    const next = { ...state.extrasByTerminal }
    let changed = false
    terminals.forEach((term) => {
      if (!next[term]) {
        const defaults = defaultCapsByTerminal[term] || { wide: 8, narrow: 4 }
        next[term] = { wide: defaults.wide, narrow: defaults.narrow }
        changed = true
      }
    })
    if (changed) {
      updateState({ extrasByTerminal: next })
    }
  }, [terminals, defaultCapsByTerminal, state.extrasByTerminal, updateState])

  const handleRuleToggle = (field: keyof WizardState["rules"], value: boolean) => {
    updateState({
      rules: {
        ...state.rules,
        [field]: value,
      },
    })
  }

  const handleMaxChange = (field: "maxCarouselsNarrow" | "maxCarouselsWide", value: string) => {
    const parsed = Math.max(1, parseInt(value, 10) || 1)
    updateState({
      rules: {
        ...state.rules,
        [field]: parsed,
      },
    })
  }

  const handleExtrasChange = (
    terminal: string,
    field: "wide" | "narrow",
    value: string
  ) => {
    const parsed = Math.max(0, parseInt(value, 10) || 0)
    updateState({
      extrasByTerminal: {
        ...state.extrasByTerminal,
        [terminal]: {
          wide: field === "wide" ? parsed : state.extrasByTerminal[terminal]?.wide || 0,
          narrow: field === "narrow" ? parsed : state.extrasByTerminal[terminal]?.narrow || 0,
        },
      },
    })
  }

  const handlePriorityChange = (index: number, value: RuleId) => {
    const base = normalizedRuleOrder.filter((rule) => rule !== value)
    base.splice(index, 0, value)

    const unique: RuleId[] = []
    base.forEach((rule) => {
      if (enabledRules.includes(rule) && !unique.includes(rule)) {
        unique.push(rule)
      }
    })
    enabledRules.forEach((rule) => {
      if (!unique.includes(rule)) {
        unique.push(rule)
      }
    })

    updateState({
      rules: {
        ...state.rules,
        ruleOrder: unique,
      },
    })
  }

  const extrasEnabled = state.rules.applyReadjustment && state.rules.ruleExtras
  const multiEnabled = state.rules.applyReadjustment && state.rules.ruleMulti

  return (
    <Card>
      <CardHeader>
        <CardTitle>Etape 6b - Capacity sizing (extras)</CardTitle>
        <CardDescription>
          Configurez les regles de readjustement et la capacite des extras par terminal.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-4">
          <h4 className="text-sm font-medium">Readjustement</h4>
          <div className="flex items-center gap-3 rounded-lg border p-4">
            <Checkbox
              checked={state.rules.applyReadjustment}
              onCheckedChange={(checked) =>
                handleRuleToggle("applyReadjustment", Boolean(checked))
              }
            />
            <Label>Appliquer les regles de readjustement</Label>
          </div>

          {state.rules.applyReadjustment && (
            <div className="space-y-4 rounded-lg border bg-muted/30 p-4">
              <div className="flex items-center gap-3">
                <Checkbox
                  checked={state.rules.ruleMulti}
                  onCheckedChange={(checked) => handleRuleToggle("ruleMulti", Boolean(checked))}
                />
                <Label>Regle 1 - Multi-carousels</Label>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="maxCarouselsNarrow">MAX_CAROUSELS_PER_FLIGHT_NARROW</Label>
                  <Input
                    id="maxCarouselsNarrow"
                    type="number"
                    min={1}
                    value={state.rules.maxCarouselsNarrow}
                    onChange={(e) => handleMaxChange("maxCarouselsNarrow", e.target.value)}
                    disabled={!multiEnabled}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="maxCarouselsWide">MAX_CAROUSELS_PER_FLIGHT_WIDE</Label>
                  <Input
                    id="maxCarouselsWide"
                    type="number"
                    min={1}
                    value={state.rules.maxCarouselsWide}
                    onChange={(e) => handleMaxChange("maxCarouselsWide", e.target.value)}
                    disabled={!multiEnabled}
                  />
                </div>
              </div>

              <div className="flex items-center gap-3">
                <Checkbox
                  checked={state.rules.ruleNarrowWide}
                  onCheckedChange={(checked) =>
                    handleRuleToggle("ruleNarrowWide", Boolean(checked))
                  }
                />
                <Label>Regle 2 - Narrow vers Wide</Label>
              </div>

              <div className="flex items-center gap-3">
                <Checkbox
                  checked={state.rules.ruleExtras}
                  onCheckedChange={(checked) => handleRuleToggle("ruleExtras", Boolean(checked))}
                />
                <Label>Regle 3 - Extras</Label>
              </div>

              {enabledRules.length > 0 && (
                <div className="space-y-3">
                  <Label className="text-sm font-medium">Ordre de priorite</Label>
                  {normalizedRuleOrder.map((rule, index) => (
                    <div key={`${rule}-${index}`} className="grid gap-3 sm:grid-cols-[120px_1fr]">
                      <Label className="text-sm text-muted-foreground">{`Priorite ${index + 1}`}</Label>
                      <Select
                        value={rule}
                        onValueChange={(value) => handlePriorityChange(index, value as RuleId)}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {enabledRules.map((item) => (
                            <SelectItem key={item} value={item}>
                              {RULE_LABELS[item]}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="space-y-4">
          <h4 className="text-sm font-medium">Capacity sizing (extras)</h4>
          {terminals.length === 0 ? (
            <Alert>
              <AlertDescription>Aucun terminal configure pour dimensionnement extra.</AlertDescription>
            </Alert>
          ) : (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Capacite standard des extra make-up par terminal.
              </p>
              {terminals.map((terminal) => {
                const caps = state.extrasByTerminal[terminal] || defaultCapsByTerminal[terminal]
                return (
                  <div key={terminal} className="grid gap-4 rounded-lg border p-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor={`extraWide-${terminal}`}>{`${terminal} - Wide capacity`}</Label>
                      <Input
                        id={`extraWide-${terminal}`}
                        type="number"
                        min={0}
                        value={caps?.wide ?? 0}
                        onChange={(e) => handleExtrasChange(terminal, "wide", e.target.value)}
                        disabled={!extrasEnabled}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor={`extraNarrow-${terminal}`}>
                        {`${terminal} - Narrow capacity`}
                      </Label>
                      <Input
                        id={`extraNarrow-${terminal}`}
                        type="number"
                        min={0}
                        value={caps?.narrow ?? 0}
                        onChange={(e) => handleExtrasChange(terminal, "narrow", e.target.value)}
                        disabled={!extrasEnabled}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        <div className="flex items-center justify-between">
          <Button variant="outline" onClick={onPrevious} className="gap-2 bg-transparent">
            <ArrowLeft className="h-4 w-4" />
            Retour
          </Button>

          <Button onClick={onNext} className="gap-2">
            Confirmer
            <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
