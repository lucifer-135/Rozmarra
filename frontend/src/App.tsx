import { Navigate, Route, Routes } from 'react-router'
import { Layout } from '@/components/Layout'
import { PatientLayout } from '@/components/PatientLayout'
import { AboutPage } from '@/pages/AboutPage'
import { MonitorPage } from '@/pages/MonitorPage'
import { PatientsPage } from '@/pages/PatientsPage'
import { PlanPage } from '@/pages/PlanPage'
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
          <Route path="monitor" element={<MonitorPage />} />
          <Route path="plan" element={<PlanPage />} />
        </Route>
        <Route path="about" element={<AboutPage />} />
        <Route path="*" element={<Navigate to="/patients" replace />} />
      </Route>
    </Routes>
  )
}
