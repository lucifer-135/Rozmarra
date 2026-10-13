import { Navigate, Route, Routes } from 'react-router'
import { Layout } from '@/components/Layout'
import { PatientLayout } from '@/components/PatientLayout'
import { PatientsPage } from '@/pages/PatientsPage'
import { PlannedScreen } from '@/pages/PlannedScreen'
import { SimulatorPage } from '@/pages/SimulatorPage'
import { VirtualPatientPage } from '@/pages/VirtualPatientPage'

// The routes of the dashboard (docs/techstack.md, Section 11.1).
export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/patients" replace />} />
        <Route path="patients" element={<PatientsPage />} />
        <Route path="patients/:id" element={<PatientLayout />}>
          <Route index element={<VirtualPatientPage />} />
          <Route path="simulator" element={<SimulatorPage />} />
          <Route path="monitor" element={<PlannedScreen screen="monitor" />} />
          <Route path="plan" element={<PlannedScreen screen="plan" />} />
        </Route>
        <Route path="about" element={<PlannedScreen screen="about" />} />
        <Route path="*" element={<Navigate to="/patients" replace />} />
      </Route>
    </Routes>
  )
}
