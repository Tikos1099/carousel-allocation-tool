declare module "react-pivottable/PivotTableUI" {
  import { ComponentType } from "react"
  const PivotTableUI: ComponentType<Record<string, unknown>>
  export default PivotTableUI
}
declare module "react-pivottable/TableRenderers" {
  const TableRenderers: Record<string, unknown>
  export default TableRenderers
}
declare module "react-pivottable/PlotlyRenderers" {
  const createPlotlyRenderers: (Plot: unknown) => Record<string, unknown>
  export default createPlotlyRenderers
}
declare module "react-pivottable/pivottable.css" {}
declare module "plotly.js-dist-min" {
  const Plotly: unknown
  export default Plotly
}
declare module "react-plotly.js/factory" {
  const createPlotlyComponent: (Plotly: unknown) => unknown
  export default createPlotlyComponent
}
