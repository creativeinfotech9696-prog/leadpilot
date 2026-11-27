import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Show, SignIn, SignUp } from "@clerk/react";
import { Toaster } from "sonner";
import ClerkAuthProvider from "@/components/auth/ClerkAuthProvider";
import AuthLayout from "@/components/auth/AuthLayout";
import Shell from "@/components/dialer/Shell";
import Overview from "@/pages/Overview";
import Lists from "@/pages/Lists";
import Clis from "@/pages/Clis";
import Timing from "@/pages/Timing";
import Directives from "@/pages/Directives";
import Uploads from "@/pages/Uploads";
import Memory from "@/pages/Memory";
import Settings from "@/pages/Settings";

const Protected = ({ children }) => (
  <>
    <Show when="signed-in">{children}</Show>
    <Show when="signed-out"><Navigate to="/sign-in" replace /></Show>
  </>
);

function App() {
  return (
    <div className="App dark">
      <BrowserRouter>
        <ClerkAuthProvider>
          <Routes>
            <Route path="/sign-in/*" element={<AuthLayout><SignIn routing="path" path="/sign-in" signUpUrl="/sign-up" withSignUp /></AuthLayout>} />
            <Route path="/sign-up/*" element={<AuthLayout><SignUp routing="path" path="/sign-up" signInUrl="/sign-in" /></AuthLayout>} />
            <Route element={<Protected><Shell /></Protected>}>
              <Route index element={<Overview />} />
              <Route path="lists" element={<Lists />} />
              <Route path="clis" element={<Clis />} />
              <Route path="timing" element={<Timing />} />
              <Route path="directives" element={<Directives />} />
              <Route path="uploads" element={<Uploads />} />
              <Route path="memory" element={<Memory />} />
              <Route path="settings" element={<Settings />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </ClerkAuthProvider>
      </BrowserRouter>
      <Toaster theme="dark" position="bottom-left" toastOptions={{ style: { background: "#141B2D", border: "1px solid #1F2B45", color: "#F1F5F9" } }} />
    </div>
  );
}

export default App;
