import { Route } from './Route';

export class Platform {
  platformNumber: string;
  color: string;
  icon: string | null;
  routes: Route[];

  constructor({
    platformNumber,
    color = '#FFFFFF',
    icon = null,
    routes = []
  }: {
    platformNumber: string;
    color?: string;
    icon?: string | null;
    routes?: Route[];
  }) {
    this.platformNumber = platformNumber;
    this.color = color;
    this.icon = icon;
    this.routes = routes;
  }

  addRoute(route: Route) {
    this.routes.push(route);
  }

  displayName() {
    return `Platform ${this.platformNumber}`;
  }
} 