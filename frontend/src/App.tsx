import { ChatPage } from "./pages/ChatPage";
import { AdminPage } from "./pages/AdminPage";

export function App() {
  if (window.location.pathname.startsWith("/admin")) return <AdminPage />;
  return <ChatPage />;
}
