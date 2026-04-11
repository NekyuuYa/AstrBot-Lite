export interface menu {
  header?: string;
  title?: string;
  icon?: string;
  to?: string;
  divider?: boolean;
  chip?: string;
  chipColor?: string;
  chipVariant?: string;
  chipIcon?: string;
  children?: menu[];
  disabled?: boolean;
  type?: string;
  subCaption?: string;
}

const sidebarItem: menu[] = [
  {
    title: 'core.navigation.welcome',
    icon: 'mdi-hand-wave-outline',
    to: '/welcome',
  },
  
  {
    title: 'core.navigation.headers.status',
    icon: 'mdi-view-dashboard',
    to: '/dashboard/default'
  },

  {
    title: 'core.navigation.headers.instances',
    icon: 'mdi-robot',
    to: '/platforms',
  },

  {
    title: 'core.navigation.commands',
    icon: 'mdi-wrench',
    to: '/commands',
  },

  {
    title: 'core.navigation.headers.agent',
    icon: 'mdi-brain',
    children: [
      {
        title: 'core.navigation.agent.providers',
        icon: 'mdi-creation',
        to: '/providers',
      },
      {
        title: 'core.navigation.agent.agentHub',
        icon: 'mdi-robot-outline',
        to: '/aar/agents'
      },
      {
        title: 'core.navigation.agent.promptRegistry',
        icon: 'mdi-script-text-outline',
        to: '/aar/prompts'
      },
      {
        title: 'core.navigation.agent.subagent',
        icon: 'mdi-vector-link',
        to: '/subagent'
      }
    ]
  },

  {
    title: 'core.navigation.headers.toolbox',
    icon: 'mdi-toolbox',
    children: [
      {
        title: 'features.tooluse.functionTools.title',
        icon: 'mdi-function-variant',
        to: '/tools'
      },
      {
        title: 'core.navigation.toolbox.mcp',
        icon: 'mdi-server-network',
        to: '/mcp'
      },
      {
        title: 'core.navigation.toolbox.skills',
        icon: 'mdi-lightning-bolt',
        to: '/skills'
      },
      {
        title: 'core.navigation.toolbox.knowledgeBase',
        icon: 'mdi-book-open-variant',
        to: '/knowledge-base',
      }
    ]
  },

  {
    title: 'core.navigation.headers.plugins',
    icon: 'mdi-puzzle',
    children: [
      {
        title: 'core.navigation.plugins.installed',
        icon: 'mdi-puzzle',
        to: '/extension/installed'
      },
      {
        title: 'core.navigation.plugins.market',
        icon: 'mdi-store',
        to: '/extension/market'
      }
    ]
  },

  {
    title: 'core.navigation.headers.monitor',
    icon: 'mdi-monitor-dashboard',
    children: [
      {
        title: 'core.navigation.monitor.console',
        icon: 'mdi-console',
        to: '/console'
      },
      {
        title: 'core.navigation.monitor.trace',
        icon: 'mdi-timeline-text-outline',
        to: '/trace'
      },
      {
        title: 'core.navigation.sessionManagement',
        icon: 'mdi-account-cog-outline',
        to: '/session-management'
      },
      {
        title: 'core.navigation.monitor.conversation',
        icon: 'mdi-database',
        to: '/conversation'
      },
      {
        title: 'core.navigation.monitor.cron',
        icon: 'mdi-clock-outline',
        to: '/cron'
      }
    ]
  },

  {
    title: 'core.navigation.headers.config',
    icon: 'mdi-cog',
    children: [
      {
        title: 'core.navigation.config.normal',
        icon: 'mdi-cog',
        to: '/config#normal'
      },
      {
        title: 'core.navigation.config.system',
        icon: 'mdi-cog-outline',
        to: '/config#system'
      }
    ]
  }
];

export default sidebarItem;
