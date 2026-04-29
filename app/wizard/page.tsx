"use client"

import { Suspense, useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { toast } from "sonner"

import { getSessionState, runJob, setSessionState, type AllocationConfig } from "@/lib/api"
import { supabase } from "@/lib/supabase"
import { AppShell } from "@/components/app-shell"
import { WizardStepper } from "@/components/wizard/wizard-stepper"
import { useI18n } from "@/lib/i18n"
import { StepUpload } from "@/components/wizard/step-upload"
import { StepColumnMapping } from "@/components/wizard/step-column-mapping"
import { StepCategoryMapping } from "@/components/wizard/step-category-mapping"
import { StepMakeupRules } from "@/components/wizard/step-makeup-rules"
import { StepTimeline } from "@/components/wizard/step-timeline"
import { StepCarousels } from "@/components/wizard/step-carousels"
import { StepExtras } from "@/components/wizard/step-extras"
import { StepRun } from "@/components/wizard/step-run"

export interface WizardState {
  file: File | null
  fileMeta?: { name: string; size: number } | null
  filePreview: Record<string, unknown>[]
  fileColumns: string[]
  suggestedMapping: AllocationConfig["columnMapping"] | null
  categoryValues: string[]
  terminalValues: string[]
  columnMapping: AllocationConfig["columnMapping"]
  mappingLocked: boolean
  categoryMapping: Record<string, "Wide" | "Narrow" | "Ignore">
  terminalMapping: Record<string, string>
  makeupRules: AllocationConfig["makeupRules"]
  timelineStep: number
  carousels: AllocationConfig["carousels"]
  rules: AllocationConfig["rules"]
  extrasByTerminal: AllocationConfig["extrasByTerminal"]
}

const initialState: WizardState = {
  file: null,
  fileMeta: null,
  filePreview: [],
  fileColumns: [],
  suggestedMapping: null,
  categoryValues: [],
  terminalValues: [],
  columnMapping: {
    departureTime: "",
    flightNumber: "",
    category: "",
    positions: "",
  },
  mappingLocked: false,
  categoryMapping: {},
  terminalMapping: {},
  makeupRules: {
    useFileColumns: true,
  },
  timelineStep: 5,
  carousels: [],
  rules: {
    applyReadjustment: true,
    ruleMulti: true,
    ruleNarrowWide: false,
    ruleExtras: true,
    maxCarouselsNarrow: 3,
    maxCarouselsWide: 2,
    ruleOrder: [],
  },
  extrasByTerminal: {},
}

export default function WizardPageWrapper() {
  return <Suspense><WizardPage /></Suspense>
}

function WizardPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const scenarioId = searchParams.get("scenarioId")
  const { t } = useI18n()
  const [currentStep, setCurrentStep] = useState(1)
  const [state, setState] = useState<WizardState>(initialState)
  const [isRunning, setIsRunning] = useState(false)
  const [isHydrated, setIsHydrated] = useState(false)

  const updateState = (updates: Partial<WizardState>) => {
    setState((prev) => ({ ...prev, ...updates }))
  }

  const canProceed = (step: number): boolean => {
    switch (step) {
      case 1:
        return state.file !== null || !!state.fileMeta
      case 2:
        return (
          state.mappingLocked &&
          !!state.columnMapping.departureTime &&
          !!state.columnMapping.flightNumber &&
          !!state.columnMapping.category &&
          !!state.columnMapping.positions
        )
      case 3:
        return Object.keys(state.categoryMapping).length > 0
      case 4:
        return (
          state.makeupRules.useFileColumns ||
          (!!state.makeupRules.wideOffsetOpen &&
            !!state.makeupRules.wideOffsetClose &&
            !!state.makeupRules.narrowOffsetOpen &&
            !!state.makeupRules.narrowOffsetClose)
        )
      case 5:
        return state.timelineStep > 0
      case 6:
        return state.carousels.length > 0
      case 7:
        return true
      default:
        return true
    }
  }

  useEffect(() => {
    let active = true

    async function loadSession() {
      try {
        const session = await getSessionState()
        if (!active || !session?.wizardState) {
          setIsHydrated(true)
          return
        }

        setState((prev) => ({
          ...prev,
          ...session.wizardState,
          file: null,
          fileMeta: session.fileMeta ?? session.wizardState.fileMeta ?? prev.fileMeta,
        }))

        if (session.currentStep) {
          const bounded = Math.min(Math.max(session.currentStep, 1), 8)
          setCurrentStep(bounded)
        }
      } finally {
        if (active) setIsHydrated(true)
      }
    }

    loadSession()

    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    if (!isHydrated) return
    const timeout = setTimeout(() => {
      const snapshot = {
        fileMeta: state.file
          ? { name: state.file.name, size: state.file.size }
          : state.fileMeta || null,
        filePreview: state.filePreview,
        fileColumns: state.fileColumns,
        suggestedMapping: state.suggestedMapping,
        categoryValues: state.categoryValues,
        terminalValues: state.terminalValues,
        columnMapping: state.columnMapping,
        mappingLocked: state.mappingLocked,
        categoryMapping: state.categoryMapping,
        terminalMapping: state.terminalMapping,
        makeupRules: state.makeupRules,
        timelineStep: state.timelineStep,
        carousels: state.carousels,
        rules: state.rules,
        extrasByTerminal: state.extrasByTerminal,
      }
      void setSessionState({ currentStep, wizardState: snapshot }).catch(() => {})
    }, 300)

    return () => clearTimeout(timeout)
  }, [state, currentStep, isHydrated])

  const handleNext = () => {
    if (currentStep < 8) {
      setCurrentStep(currentStep + 1)
    }
  }

  const handlePrevious = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1)
    }
  }

  const handleRunAllocation = async () => {
    if (!state.file && !state.fileMeta) return

    setIsRunning(true)
    toast.info(t.wizard.toastRunning, { duration: 2000 })

    try {
      const config: AllocationConfig = {
        columnMapping: state.columnMapping,
        categoryMapping: state.categoryMapping,
        terminalMapping: state.terminalMapping,
        makeupRules: state.makeupRules,
        timelineStep: state.timelineStep,
        carousels: state.carousels,
        rules: state.rules,
        extrasByTerminal: state.extrasByTerminal,
      }

      const scenarioName =
        typeof window !== "undefined"
          ? (window.sessionStorage.getItem("carousel_scenario_name") ?? undefined)
          : undefined
      const { jobId } = await runJob(state.file, config, scenarioName)

      // If launched from a scenario, save the run to allocation_runs and navigate back
      if (scenarioId) {
        await supabase.from("allocation_runs").insert({
          id: jobId,
          scenario_id: scenarioId,
          name: scenarioName || null,
          status: "done",
          config: config as unknown as Record<string, unknown>,
          kpis: null,
          analytics: null,
          warnings: null,
          storage_size_bytes: 0,
          finished_at: new Date().toISOString(),
        })
        toast.success(t.wizard.toastSuccess, { duration: 3000 })
        router.push(`/scenario/${scenarioId}/allocation`)
        return
      }

      toast.success(t.wizard.toastSuccess, { duration: 3000 })

      // Redirect to results
      router.push(`/results?jobId=${jobId}`)
    } catch (error) {
      toast.error(t.wizard.toastError, {
        description: error instanceof Error ? error.message : String(error),
      })
      setIsRunning(false)
    }
  }

  const renderStep = () => {
    switch (currentStep) {
      case 1:
        return (
          <StepUpload
            state={state}
            updateState={updateState}
            onNext={handleNext}
          />
        )
      case 2:
        return (
          <StepColumnMapping
            state={state}
            updateState={updateState}
            onNext={handleNext}
            onPrevious={handlePrevious}
          />
        )
      case 3:
        return (
          <StepCategoryMapping
            state={state}
            updateState={updateState}
            onNext={handleNext}
            onPrevious={handlePrevious}
          />
        )
      case 4:
        return (
          <StepMakeupRules
            state={state}
            updateState={updateState}
            onNext={handleNext}
            onPrevious={handlePrevious}
          />
        )
      case 5:
        return (
          <StepTimeline
            state={state}
            updateState={updateState}
            onNext={handleNext}
            onPrevious={handlePrevious}
          />
        )
      case 6:
        return (
          <StepCarousels
            state={state}
            updateState={updateState}
            onNext={handleNext}
            onPrevious={handlePrevious}
          />
        )
      case 7:
        return (
          <StepExtras
            state={state}
            updateState={updateState}
            onNext={handleNext}
            onPrevious={handlePrevious}
          />
        )
      case 8:
        return (
          <StepRun
            state={state}
            isRunning={isRunning}
            onRun={handleRunAllocation}
            onPrevious={handlePrevious}
          />
        )
      default:
        return null
    }
  }

  const steps = t.wizard.steps.map((s, i) => ({ id: i + 1, ...s }))

  return (
    <AppShell>
      <div className="container mx-auto max-w-5xl px-4 py-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold">{t.wizard.title}</h1>
          <p className="mt-1 text-muted-foreground">{t.wizard.subtitle}</p>
        </div>

        <WizardStepper steps={steps} currentStep={currentStep} />

        <div className="mt-8">{renderStep()}</div>
      </div>
    </AppShell>
  )
}
