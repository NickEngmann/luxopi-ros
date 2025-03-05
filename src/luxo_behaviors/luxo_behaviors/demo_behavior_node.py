class DemoBehaviorNode(Node):
    def __init__(self):
        super().__init__('demo_behavior_node')
        # Ensure the run_demo parameter is properly processed
        self.run_demo = self.declare_parameter('run_demo', False).value
        self.get_logger().info(f'Demo behavior initialized with run_demo={self.run_demo}')
        
        if self.run_demo:
            self.get_logger().info('Demo mode is active, starting behaviors...')
            # Make sure demo behaviors are actually triggered
            self.timer = self.create_timer(1.0, self.run_demo_sequence)
        else:
            self.get_logger().info('Demo mode is not active')
    
    def run_demo_sequence(self):
        # Log so we can see this is being called
        self.get_logger().info('Running demo sequence')
        # Your demo sequence implementation
