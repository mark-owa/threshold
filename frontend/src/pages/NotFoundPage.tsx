import { Link } from "react-router-dom";
import { Compass } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/Feedback";

export function NotFoundPage() {
  return (
    <EmptyState
      icon={<Compass size={18} />}
      title="Page not found"
      description="That page doesn't exist, or it was moved."
      action={
        <Link to="/overview">
          <Button variant="primary">Back to overview</Button>
        </Link>
      }
    />
  );
}
