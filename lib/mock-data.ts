// Mock data for the Carousel Allocation Tool

export interface Flight {
  id: string
  departureTime: string
  makeupOpening: string
  makeupClosing: string
  flightNumber: string
  category: "Wide" | "Narrow"
  terminal: string
  positions: number
  assignedCarousel: string | null
  unassignedReason: string | null
}

export interface Carousel {
  id: string
  terminal: string
  carouselName: string
  wideCapacity: number
  narrowCapacity: number
}

export interface KPIs {
  totalFlights: number
  assignedFlights: number
  unassignedFlights: number
  assignmentRate: number
  extraMakeupsNeeded: Record<string, number>
  mostConstrainedTerminal: string
  peakOccupancyWindow: string
}

export interface JobResult {
  jobId: string
  status: "completed" | "running" | "failed"
  createdAt: string
  completedAt: string | null
  flights: Flight[]
  kpis: KPIs
  unassignedReasons: { reason: string; count: number }[]
  capacitySizing: { terminal: string; extrasNeeded: number; peakTime: string }[]
  timelineData: { time: string; occupied: number; capacity: number }[]
  unassignedByTerminal: { terminal: string; count: number }[]
}

// Mock Excel preview data
export const mockExcelPreview = [
  { STD: "2024-03-15 06:00", FlightNo: "AF1234", Type: "J", Positions: 3, Terminal: "T1", Open: "04:30", Close: "05:45" },
  { STD: "2024-03-15 06:15", FlightNo: "BA5678", Type: "M", Positions: 2, Terminal: "T2", Open: "04:45", Close: "06:00" },
  { STD: "2024-03-15 06:30", FlightNo: "LH9012", Type: "J", Positions: 4, Terminal: "T1", Open: "05:00", Close: "06:15" },
  { STD: "2024-03-15 06:45", FlightNo: "KL3456", Type: "M", Positions: 2, Terminal: "T2", Open: "05:15", Close: "06:30" },
  { STD: "2024-03-15 07:00", FlightNo: "AF7890", Type: "J", Positions: 3, Terminal: "T1", Open: "05:30", Close: "06:45" },
  { STD: "2024-03-15 07:15", FlightNo: "IB1122", Type: "M", Positions: 2, Terminal: "T3", Open: "05:45", Close: "07:00" },
  { STD: "2024-03-15 07:30", FlightNo: "AZ3344", Type: "J", Positions: 4, Terminal: "T1", Open: "06:00", Close: "07:15" },
  { STD: "2024-03-15 07:45", FlightNo: "SN5566", Type: "M", Positions: 2, Terminal: "T2", Open: "06:15", Close: "07:30" },
  { STD: "2024-03-15 08:00", FlightNo: "UA7788", Type: "J", Positions: 3, Terminal: "T1", Open: "06:30", Close: "07:45" },
  { STD: "2024-03-15 08:15", FlightNo: "DL9900", Type: "M", Positions: 2, Terminal: "T3", Open: "06:45", Close: "08:00" },
  { STD: "2024-03-15 08:30", FlightNo: "AA1133", Type: "J", Positions: 4, Terminal: "T2", Open: "07:00", Close: "08:15" },
  { STD: "2024-03-15 08:45", FlightNo: "EK2244", Type: "J", Positions: 5, Terminal: "T1", Open: "07:15", Close: "08:30" },
  { STD: "2024-03-15 09:00", FlightNo: "QR3355", Type: "M", Positions: 2, Terminal: "T3", Open: "07:30", Close: "08:45" },
  { STD: "2024-03-15 09:15", FlightNo: "TK4466", Type: "J", Positions: 3, Terminal: "T2", Open: "07:45", Close: "09:00" },
  { STD: "2024-03-15 09:30", FlightNo: "EY5577", Type: "M", Positions: 2, Terminal: "T1", Open: "08:00", Close: "09:15" },
  { STD: "2024-03-15 09:45", FlightNo: "SQ6688", Type: "J", Positions: 4, Terminal: "T3", Open: "08:15", Close: "09:30" },
  { STD: "2024-03-15 10:00", FlightNo: "CX7799", Type: "M", Positions: 2, Terminal: "T2", Open: "08:30", Close: "09:45" },
  { STD: "2024-03-15 10:15", FlightNo: "JL8800", Type: "J", Positions: 3, Terminal: "T1", Open: "08:45", Close: "10:00" },
  { STD: "2024-03-15 10:30", FlightNo: "NH9911", Type: "M", Positions: 2, Terminal: "T3", Open: "09:00", Close: "10:15" },
  { STD: "2024-03-15 10:45", FlightNo: "OZ0022", Type: "J", Positions: 4, Terminal: "T2", Open: "09:15", Close: "10:30" },
]

// Mock category values found in file
export const mockCategoryValues = ["J", "M", "W", "N", "X"]
export const mockTerminalValues = ["T1", "T2", "T3", "2E", "2F", "CDG1"]

// Mock carousels data
export const mockCarousels: Carousel[] = [
  { id: "1", terminal: "T1", carouselName: "MU-101", wideCapacity: 4, narrowCapacity: 6 },
  { id: "2", terminal: "T1", carouselName: "MU-102", wideCapacity: 4, narrowCapacity: 6 },
  { id: "3", terminal: "T1", carouselName: "MU-103", wideCapacity: 3, narrowCapacity: 5 },
  { id: "4", terminal: "T2", carouselName: "MU-201", wideCapacity: 4, narrowCapacity: 6 },
  { id: "5", terminal: "T2", carouselName: "MU-202", wideCapacity: 4, narrowCapacity: 6 },
  { id: "6", terminal: "T3", carouselName: "MU-301", wideCapacity: 3, narrowCapacity: 5 },
  { id: "7", terminal: "T3", carouselName: "MU-302", wideCapacity: 3, narrowCapacity: 5 },
]

// Mock job result
export const mockJobResult: JobResult = {
  jobId: "job-2024-001",
  status: "completed",
  createdAt: "2024-03-15T08:00:00Z",
  completedAt: "2024-03-15T08:02:30Z",
  flights: [
    { id: "1", departureTime: "2024-03-15 06:00", makeupOpening: "04:30", makeupClosing: "05:45", flightNumber: "AF1234", category: "Wide", terminal: "T1", positions: 3, assignedCarousel: "MU-101", unassignedReason: null },
    { id: "2", departureTime: "2024-03-15 06:15", makeupOpening: "04:45", makeupClosing: "06:00", flightNumber: "BA5678", category: "Narrow", terminal: "T2", positions: 2, assignedCarousel: "MU-201", unassignedReason: null },
    { id: "3", departureTime: "2024-03-15 06:30", makeupOpening: "05:00", makeupClosing: "06:15", flightNumber: "LH9012", category: "Wide", terminal: "T1", positions: 4, assignedCarousel: "MU-102", unassignedReason: null },
    { id: "4", departureTime: "2024-03-15 06:45", makeupOpening: "05:15", makeupClosing: "06:30", flightNumber: "KL3456", category: "Narrow", terminal: "T2", positions: 2, assignedCarousel: "MU-202", unassignedReason: null },
    { id: "5", departureTime: "2024-03-15 07:00", makeupOpening: "05:30", makeupClosing: "06:45", flightNumber: "AF7890", category: "Wide", terminal: "T1", positions: 3, assignedCarousel: "MU-103", unassignedReason: null },
    { id: "6", departureTime: "2024-03-15 07:15", makeupOpening: "05:45", makeupClosing: "07:00", flightNumber: "IB1122", category: "Narrow", terminal: "T3", positions: 2, assignedCarousel: "MU-301", unassignedReason: null },
    { id: "7", departureTime: "2024-03-15 07:30", makeupOpening: "06:00", makeupClosing: "07:15", flightNumber: "AZ3344", category: "Wide", terminal: "T1", positions: 4, assignedCarousel: null, unassignedReason: "Capacite_insuffisante" },
    { id: "8", departureTime: "2024-03-15 07:45", makeupOpening: "06:15", makeupClosing: "07:30", flightNumber: "SN5566", category: "Narrow", terminal: "T2", positions: 2, assignedCarousel: "MU-201", unassignedReason: null },
    { id: "9", departureTime: "2024-03-15 08:00", makeupOpening: "06:30", makeupClosing: "07:45", flightNumber: "UA7788", category: "Wide", terminal: "T1", positions: 3, assignedCarousel: "MU-101", unassignedReason: null },
    { id: "10", departureTime: "2024-03-15 08:15", makeupOpening: "06:45", makeupClosing: "08:00", flightNumber: "DL9900", category: "Narrow", terminal: "T3", positions: 2, assignedCarousel: "MU-302", unassignedReason: null },
    { id: "11", departureTime: "2024-03-15 08:30", makeupOpening: "07:00", makeupClosing: "08:15", flightNumber: "AA1133", category: "Wide", terminal: "T2", positions: 4, assignedCarousel: null, unassignedReason: "Conflit_horaire" },
    { id: "12", departureTime: "2024-03-15 08:45", makeupOpening: "07:15", makeupClosing: "08:30", flightNumber: "EK2244", category: "Wide", terminal: "T1", positions: 5, assignedCarousel: "MU-102", unassignedReason: null },
  ],
  kpis: {
    totalFlights: 156,
    assignedFlights: 148,
    unassignedFlights: 8,
    assignmentRate: 94.9,
    extraMakeupsNeeded: { T1: 2, T2: 1, T3: 0 },
    mostConstrainedTerminal: "T1",
    peakOccupancyWindow: "07:00 - 08:30",
  },
  unassignedReasons: [
    { reason: "Capacite_insuffisante", count: 5 },
    { reason: "Conflit_horaire", count: 2 },
    { reason: "Terminal_non_configure", count: 1 },
  ],
  capacitySizing: [
    { terminal: "T1", extrasNeeded: 2, peakTime: "07:30" },
    { terminal: "T2", extrasNeeded: 1, peakTime: "08:15" },
    { terminal: "T3", extrasNeeded: 0, peakTime: "09:00" },
  ],
  timelineData: [
    { time: "04:00", occupied: 0, capacity: 20 },
    { time: "04:30", occupied: 3, capacity: 20 },
    { time: "05:00", occupied: 7, capacity: 20 },
    { time: "05:30", occupied: 12, capacity: 20 },
    { time: "06:00", occupied: 16, capacity: 20 },
    { time: "06:30", occupied: 19, capacity: 20 },
    { time: "07:00", occupied: 22, capacity: 20 },
    { time: "07:30", occupied: 24, capacity: 20 },
    { time: "08:00", occupied: 21, capacity: 20 },
    { time: "08:30", occupied: 18, capacity: 20 },
    { time: "09:00", occupied: 14, capacity: 20 },
    { time: "09:30", occupied: 10, capacity: 20 },
    { time: "10:00", occupied: 6, capacity: 20 },
    { time: "10:30", occupied: 3, capacity: 20 },
    { time: "11:00", occupied: 1, capacity: 20 },
  ],
  unassignedByTerminal: [
    { terminal: "T1", count: 5 },
    { terminal: "T2", count: 2 },
    { terminal: "T3", count: 1 },
  ],
}

// Available columns for mapping
export const availableColumns = ["STD", "FlightNo", "Type", "Positions", "Terminal", "Open", "Close", "Gate", "Airline", "Destination"]

// Download files available
export const downloadFiles = [
  { name: "summary.csv", label: "Resume (CSV)", available: true },
  { name: "summary.txt", label: "Resume (TXT)", available: true },
  { name: "timeline.xlsx", label: "Timeline", available: true },
  { name: "heatmap_positions_occupied.xlsx", label: "Heatmap - Positions Occupees", available: true },
  { name: "heatmap_positions_free.xlsx", label: "Heatmap - Positions Libres", available: true },
  { name: "timeline_readjusted.xlsx", label: "Timeline Reajustee", available: true },
  { name: "extra_makeups_needed.csv", label: "Make-ups Supplementaires", available: true },
]
