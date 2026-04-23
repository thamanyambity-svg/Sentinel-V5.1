import { createTRPCReact } from "@trpc/react-query";
import type { AppRouter } from "../server/_core/router";

/**
 * TRPC React Hook
 * Utiliser dans les composants pour faire des queries/mutations
 */
export const trpc = createTRPCReact<AppRouter>();
