import { initTRPC } from "@trpc/server";
import { ZodError } from "zod";

/**
 * Initialiser TRPC
 */
const t = initTRPC.create({
  errorFormatter({ shape, error }) {
    return {
      ...shape,
      data: {
        ...shape.data,
        zodError:
          error.cause instanceof ZodError ? error.cause.flatten() : null,
      },
    };
  },
});

/**
 * Middleware d'authentification
 */
export const middleware = t.middleware;

/**
 * Export pour utilisation
 */
export const router = t.router;
export const publicProcedure = t.procedure;
