import {
  Navigate,
  RouterProvider,
  Route,
  Outlet,
  createBrowserRouter,
  createRoutesFromElements,
} from 'react-router-dom';

import { Toolbar } from './components/Layout/Toolbar';
import { WorkflowsListPage } from './pages/WorkflowsListPage';
import { WorkflowEditorPage } from './pages/WorkflowEditorPage';
import { ExecutionsListPage } from './pages/ExecutionsListPage';
import { ExecutionDetailPage } from './pages/ExecutionDetailPage';

function RootLayout() {
  return (
    <div className="min-h-screen flex flex-col">
      <Toolbar />
      <div className="flex-1 min-h-0">
        <Outlet />
      </div>
    </div>
  );
}

const router = createBrowserRouter(
  createRoutesFromElements(
    <Route element={<RootLayout />}>
      <Route path="/" element={<Navigate to="/workflows" replace />} />

      <Route path="/workflows" element={<WorkflowsListPage />} />
      <Route path="/workflows/:slug" element={<WorkflowEditorPage />} />

      <Route path="/executions" element={<ExecutionsListPage />} />
      <Route path="/executions/:executionId" element={<ExecutionDetailPage />} />
    </Route>,
  ),
);

export function AppRouterProvider() {
  return <RouterProvider router={router} />;
}
